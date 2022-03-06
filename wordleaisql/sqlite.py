# -*- coding: utf-8 -*-

"""
SQLite backend.

Tables are named by the following convention:

{vocabname}_words   : contains all words
{vocabname}_judges  : contains judge results for all word pairs
"""

import os
import sqlite3
import math
import random
from contextlib import contextmanager
from logging import getLogger
logger = getLogger(__name__)

from .utils import all_wordle_judges, _timereport, _dedup, WordEvaluation, wordle_judge, encode_judgement, _read_vocabfile
from .base import WordleAI


def _setup(dbfile: str, vocabname: str, words: list, use_cpp: bool=True, recompile: bool=False, compiler: str=None):
    assert len(words) == len(set(words)), "input_words must be unique"
    wordlens = set(len(w) for w in words)
    assert len(wordlens) == 1, "word length must be equal, but '{}'".format(wordlens)
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=OFF")  # disable rollback to save time        
        
        c.execute('DROP TABLE IF EXISTS "{name}_words"'.format(name=vocabname))
        c.execute('CREATE TABLE "{name}_words" (word TEXT PRIMARY KEY)'.format(name=vocabname))
        params = [(w,) for w in words]
        c.executemany('INSERT INTO "{name}_words" VALUES (?)'.format(name=vocabname), params)
        c.execute('CREATE INDEX "{name}_words_idx" ON "{name}_words" (word)'.format(name=vocabname))

        with _timereport("Precomputing wordle judges"):
            c.execute('DROP TABLE IF EXISTS "{name}_judges"'.format(name=vocabname))
            c.execute('CREATE TABLE "{name}_judges" (input_word TEXT, answer_word TEXT, judge INT)'.format(name=vocabname))
            params = all_wordle_judges(words, use_cpp=use_cpp, recompile=recompile, compiler=compiler)
            c.executemany('INSERT INTO "{name}_judges" VALUES (?,?,?)'.format(name=vocabname), params)

        with _timereport("Creating indices"):
            c.execute('CREATE INDEX "{name}_judge_idx" ON "{name}_judges" (input_word, judge)'.format(name=vocabname))
            c.execute('CREATE INDEX "{name}_judge_idx2" ON "{name}_judges" (answer_word)'.format(name=vocabname))
        conn.commit()

def _evaluate(dbfile: str, vocabname: str, top_k: int=20, criterion: str="mean_entropy", candidates: list=None)-> list:
    with sqlite3.connect(dbfile) as conn:
        conn.create_function("log2", 1, math.log2)
        c = conn.cursor()
        # find the number of all words and compare with the number of candidates
        # if they are the same, then we do not need to filter answer_word
        c.execute('SELECT count(*) FROM "{name}_words"'.format(name=vocabname))
        n_words = c.fetchone()[0]

        if candidates is None or len(candidates) >= n_words:  # all words are in the candidates
            params = None
            answer_filter = ""
        else:
            candidate_set = set(candidates)
            params = tuple(candidate_set)
            answer_filter = "WHERE answer_word IN (%s)" % ",".join("?" * len(params))

        q = """
        with tmp AS (
          SELECT
            input_word,
            judge,
            count(*) AS n,
            log2(count(*)) AS entropy
          FROM
            "{name}_judges"
          {answerfilter}
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
        """.format(answerfilter=answer_filter, name=vocabname)
        #print(q)
        if params is None:
            c.execute(q)
        else:
            c.execute(q, params)

        candidate_set = None if candidates is None else set(candidates)
        out = [row + (1 if candidate_set is None else int(row[0] in candidate_set),) for row in c]
    out = [WordEvaluation(*row) for row in out]
    out.sort(key=lambda row: (getattr(row, criterion), -row.is_candidate))
    return out[:top_k]

def _vocabnames(dbfile: str)-> list:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master")
        tables = [row[0] for row in c]
        t1 = [t[:-6] for t in tables if t.endswith("_words")]
        t2 = [t[:-7] for t in tables if t.endswith("_judges")]
        out = list(set(t1) & set(t2))  # we need both _words and _judges tables
    return out

def _words(dbfile: str, vocabname: str)-> list:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM "{name}_words"'.format(name=vocabname))
        words = [row[0] for row in c]
    return words


class WordleAISQLite(WordleAI):
    """
    Wordle AI with SQLite backend

    Vocab information is stored in {vocabname}_words and {vocabname}_judges

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
    def __init__(self, vocabname: str, words: list or str=None, dbfile: str=None,
                 decision_metric: str="mean_entropy", candidate_weight: float=0.3, strength: float=6,
                 use_cpp: bool=True, cpp_recompile: bool=False, cpp_compiler: str=None, resetup: bool=False, **kwargs):
        if dbfile is None:
            dbfile = os.environ.get("WORDLEAISQL_DBFILE")
            if dbfile is None:
                dbfile = "./wordleai.db"
        os.makedirs(os.path.dirname(os.path.abspath(dbfile)), exist_ok=True)
        self.dbfile = dbfile
        logger.info("SQLite database: '%s'", self.dbfile)
        self.vocabname = vocabname
        self.decision_metric = decision_metric
        self.candidate_weight = candidate_weight
        self.strength = min(max(strength, 0), 10)  # clip to [0, 10]
        # strength is linearly converted to the power of noise: 0 -> +5, 10 -> -5
        # larger noise, close to random decision
        self.decision_noise = math.pow(10, 5-self.strength)

        if resetup or (vocabname not in self.vocabnames):
            assert words is not None, "`words` must be supplied to setup the vocab '{}'".format(vocabname)
            words = _read_vocabfile(words) if type(words) == str else _dedup(words)
            with _timereport("Setup tables for vocabname '%s'" % vocabname):
                _setup(dbfile=dbfile, vocabname=vocabname, words=words, use_cpp=use_cpp, recompile=cpp_recompile, compiler=cpp_compiler)

        self._info = []                  # infomation of the judge results
        self._nonanswer_words = set([])  # words that cannot become an answer
        #self.set_candidates()

    @property
    def name(self)-> str:
        return "Wordle AI (SQLite backend)"

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
        return _evaluate(self.dbfile, self.vocabname, top_k=top_k, criterion=criterion, candidates=self.candidates)
    
    def pick_word(self):
        num_remain = len(self.candidates)
        #print(count, candidates)
        if num_remain == 1:
            return self.candidates[0]
        elif num_remain == 0:
            print("Warning: No candidates left. This is a random choice")
            return random.choice(self.words)

        results = self.evaluate(top_k=10000, criterion=self.decision_metric)
        #print(results[:10], len(results))        
        words = [row.input_word for row in results]
        scores = [getattr(row, self.decision_metric) for row in results]  # score of eadch word, the smaller the better
        if self.decision_metric in ("mean_n", "max_n"):
            # we take log of the score to adjust for the scale
            # add 1p just in case to avoid the zero error
            scores = [math.log1p(s) for s in scores]
        
        # Flip the sign and adjust for the candidates
        for i, row in enumerate(results):
            scores[i] = row.is_candidate * self.candidate_weight - scores[i]
        # Subtract the maximum to avoid overflow
        maxscore = max(scores)
        scores = [s - maxscore for s in scores]
        # Add randomness
        weights = [math.exp(s / self.decision_noise) for s in scores]
        
        out = random.choices(words, weights=weights, k=1)
        return out[0]