# -*- coding: utf-8 -*-

"""
SQLite backend with no precomputation.

A quick version where the judge results are not precomputed.

Only table created:
    {vocabname}_words_approx   : contains all words
"""

import os
import math
import random
import sqlite3
from logging import getLogger
logger = getLogger(__name__)

from .utils import WordEvaluation, wordle_judge, _read_vocabfile, _dedup
from .sqlite import WordleAISQLite

def _setup(dbfile: str, vocabname: str, words: list, use_cpp: bool=True, recompile: bool=False, compiler: str=None):
    assert len(words) == len(set(words)), "input_words must be unique"
    wordlens = set(len(w) for w in words)
    assert len(wordlens) == 1, "word length must be equal, but '{}'".format(wordlens)
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS "{name}_words_approx"'.format(name=vocabname))
        c.execute('CREATE TABLE "{name}_words_approx" (word TEXT PRIMARY KEY)'.format(name=vocabname))
        params = [(w,) for w in words]
        c.executemany('INSERT INTO "{name}_words_approx" VALUES (?)'.format(name=vocabname), params)
        c.execute('CREATE INDEX "{name}_words_approx_idx" ON "{name}_words_approx" (word)'.format(name=vocabname))
        conn.commit()

def _evaluate(dbfile: str, vocabname: str, top_k: int=20, criterion: str="mean_entropy",
              candidates: list=None, approxlevel: int=1000000)-> list:
    allwords = _words(dbfile, vocabname)  # get all words
    if candidates is None:
        candidates = allwords
    # sample word so that len(words) * len(candidates) <= sizelimit
    samplesize = max(1, int(approxlevel / len(candidates)))
    logger.info("Input word size limit: %d", samplesize)
    words = allwords if samplesize >= len(allwords) else random.sample(allwords, samplesize)
    # if all words are included, we don't need filter
    if len(words) == len(allwords):
        words = None
    if len(candidates) == len(allwords):
        candidates = None

    with sqlite3.connect(dbfile) as conn:
        conn.create_function("log2", 1, math.log2)
        conn.create_function("WordleJudge", 2, wordle_judge)
        c = conn.cursor()

        if words is None:
            inputfilter = ""
            params1 = ()
        else:
            inputfilter = "WHERE word IN ({})".format(",".join("?" * len(words)))
            params1 = tuple(words)

        #print(candidates)
        if candidates is None:
            answerfilter = ""
            params2 = ()
        else:
            answerfilter = "WHERE word IN ({})".format(",".join("?" * len(candidates)))
            params2 = tuple(candidates)
        #print(answerfilter)
        params = params1 + params2

        q = """
        with judges AS (
          SELECT
            a.word AS input_word,
            b.word AS answer_word,
            WordleJudge(a.word, b.word) AS judge
          FROM
            (SELECT word FROM {vocabname}_words_approx {inputfilter}) AS a,
            (SELECT word FROM {vocabname}_words_approx {answerfilter}) AS b
        ),
        tmp AS (
          SELECT
            input_word,
            judge,
            count(*) AS n,
            log2(count(*)) AS entropy
          FROM
            "judges"
          GROUP BY
            input_word, judge
        )
        SELECT
          input_word,
          max(n) AS max_n,
          1.0 * sum(n*n) / sum(n) AS mean_n,
          sum(n*entropy) / sum(n) AS mean_entropy
        FROM
          tmp
        GROUP BY
          input_word    
        """.format(vocabname=vocabname, inputfilter=inputfilter, answerfilter=answerfilter)
        #print(q)
        #print(len(params1), len(params2))
        #print(s)
        if len(params)==0:
            c.execute(q)
        else:
            c.execute(q, params)
        candidate_set = None if candidates is None else set(candidates)
        out = {row[0]: row + (1 if candidate_set is None else int(row[0] in candidate_set), 1) for row in c}
        # we add a flag indicating the eval is done at the end to distinguish from the padded rows
    # we pad random evals is there are insufficient rows
    for w in allwords:
        if len(out) >= top_k:
            break
        if w in out:
            continue
        out[w] = (w, 0, 0.0, 0.0, int(w in candidate_set), 0)
    out = [(WordEvaluation(*row[:-1]), row[-1]) for row in out.values()]
    out.sort(key=lambda row: (-row[1], getattr(row[0], criterion), -row[0].is_candidate))
    out = out[:top_k]
    out = [row[0] for row in out]
    return out

def _vocabnames(dbfile: str)-> list:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master")
        tables = [row[0] for row in c]
        #print(tables)
        t = [t[:-13] for t in tables if t.endswith("_words_approx")]
    return t

def _words(dbfile: str, vocabname: str)-> list:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM "{name}_words_approx"'.format(name=vocabname))
        words = [row[0] for row in c]
    return words


class WordleAIApprox(WordleAISQLite):
    """
    Wordle AI with SQLite backend without precomputation.

    By omitting precomputation, this class computes approximation results
    faster and with smaller storage.

    Vocab information is stored in {vocabname}_words

    Args:
        vocabname (str):
            Name of vocaburary
        words (str of list): 
            If str, the path to a vocabulary file
            If list, the list of words
            Can be omitted if the vocabname is already in the database and resetup=False
        dbfile (str):
            SQLite database file
            If not supplied, use environment variable `WORDLEAISQL_DBFILE` if exists,
            otherwise './wordleai.db' in the current directory is used
        approxlevel (int):
            Limit of the len(input_words) * len(candidates) to compute the evaluation.
            The larger, the more accurate approximation.

        decision_metric (str):
            The criteria to pick a word
            Either 'max_n', 'mean_n', of 'mean_entropy'
        candidate_weight (float):
            The weight added to the answer candidate word when picking a word
        strength (float):
            AI strength in [0, 10]

        use_cpp (bool):
            Use C++ code to precompute wodle judgements when available
        cpp_recompile (bool):
            Compile the C++ code again if the source code has no change
        cpp_compiler (str):
            Command name of the C++ compiler. If None, 'g++' and 'clang++' are searched

        resetup (bool):
            Setup again if the vocabname already exists
    """
    def __init__(self, vocabname: str, words: list or str=None, dbfile: str=None, approxlevel: int=1000000,
                 decision_metric: str="mean_entropy", candidate_weight: float=0.3, strength: float=6,
                 use_cpp: bool=True, cpp_recompile: bool=False, cpp_compiler: str=None, resetup: bool=False, **kwargs):
        if dbfile is None:
            dbfile = os.environ.get("WORDLEAISQL_DBFILE")
            if dbfile is None:
                dbfile = "./wordleai.db"
        os.makedirs(os.path.dirname(os.path.abspath(dbfile)), exist_ok=True)
        self.dbfile = dbfile
        assert approxlevel > 0
        self.approxlevel = approxlevel
        logger.info("SQLite database: '%s', approxlevel: %d", self.dbfile, self.approxlevel)
        self.vocabname = vocabname
        self.decision_metric = decision_metric
        self.candidate_weight = candidate_weight
        self.strength = min(max(strength, 0), 10)  # clip to [0, 10]
        # strength is linearly converted to the power of noise: 0 -> +5, 10 -> -5
        # larger noise, close to random decision
        self.decision_noise = math.pow(10, 5-self.strength)

        #print("vocabnames", self.vocabnames)
        if resetup or (vocabname not in self.vocabnames):
            assert words is not None, "`words` must be supplied to setup the vocab '{}'".format(vocabname)
            words = _read_vocabfile(words) if type(words) == str else _dedup(words)
            logger.info("Setup tables for vocabname '%s'", vocabname)
            _setup(dbfile=dbfile, vocabname=vocabname, words=words, use_cpp=use_cpp, recompile=cpp_recompile, compiler=cpp_compiler)

        self.set_candidates()

    @property
    def name(self)-> str:
        return "Wordle AI (SQLite backend, approx)"

    @property
    def vocabnames(self)-> list:
        """Available vocab names"""
        return _vocabnames(self.dbfile)
    
    @property
    def words(self)-> list:
        """All words that can be inputted"""
        return _words(self.dbfile, self.vocabname)

    def evaluate(self, top_k: int=20, criterion: str="mean_entropy")-> list:
        """
        Evaluate input words and return the top ones in accordance with the given criterion
        """
        return _evaluate(self.dbfile, self.vocabname, top_k=top_k, criterion=criterion,
                         candidates=self.candidates, approxlevel=self.approxlevel)