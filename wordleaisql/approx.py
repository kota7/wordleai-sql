# -*- coding: utf-8 -*-

"""
SQLite backend with no precomputation.

A quick version where the judge results are not precomputed.

Only table created:
    {vocabname}_words_approx   : contains all words
"""

import os
import sys
import math
import random
import sqlite3
from contextlib import contextmanager
from logging import getLogger
logger = getLogger(__name__)

from .utils import WordEvaluation, wordle_judge, _read_vocabfile, _dedup
from .sqlite import WordleAISQLite

@contextmanager
def _connect(db: str or sqlite3.Connection)-> sqlite3.Connection:
    if type(db) == sqlite3.Connection:
        yield db
    elif type(db) == str:
        conn = sqlite3.connect(db)
        try:
            yield conn
        finally:
            conn.close()
    else:
        raise TypeError("`db` must be either str or sqlite3.Connection, but '{}'".format(type(db)))

def _setup(db: str or sqlite3.Connection, vocabname: str, words: list or dict):
    assert len(words) == len(set(words)), "input_words must be unique"
    wordlens = set(len(w) for w in words)
    assert len(wordlens) == 1, "word length must be equal, but '{}'".format(wordlens)
    #with sqlite3.connect(dbfile) as conn:
    with _connect(db) as conn:
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS "{name}_words_approx"'.format(name=vocabname))
        c.execute('CREATE TABLE "{name}_words_approx" (word TEXT PRIMARY KEY, weight FLOAT)'.format(name=vocabname))
        params = (
            words.items() if isinstance(words, dict) else
            [(w, 1) for w in words] if isinstance(words, list) else
            None
        )
        if params is None:
            raise TypeError("Unsupported type of `words`, '{}'".format(type(words)))
        c.executemany('INSERT INTO "{name}_words_approx" VALUES (?,?)'.format(name=vocabname), params)
        c.execute('CREATE INDEX "{name}_words_approx_idx" ON "{name}_words_approx" (word)'.format(name=vocabname))
        conn.commit()

# def _ensure_word_weight_column(dbfile: str, vocabname: str):
#     """If weight column is missing in the words table, add it with a constant 1"""
#     with sqlite3.connect(dbfile) as conn:
#         c = conn.cursor()
#         # check the existing column
#         c.execute('SELECT * FROM "{name}_words_approx" LIMIT 1'.format(name=vocabname))
#         exist = any(col[0].lower() == "weight" for col in c.description)
#         if not exist:
#             c.execute('ALTER TABLE "{name}_words_approx" ADD weight FLOAT'.format(name=vocabname))
#             logger.info('Added column `"%s_words_approx".weight`', vocabname)
#             c.execute('UPDATE "{name}_words_approx" SET weight = 1.0'.format(name=vocabname))
#             logger.info('Filled `"%s_words_approx".weight` with ones', vocabname)
#         conn.commit()

def _evaluate(db: str or sqlite3.Connection, vocabname: str, top_k: int=20, criterion: str="mean_entropy", candidates: list=None,
              word_pair_limit: int=500000, candidate_samplesize: int=500)-> list:
    assert candidate_samplesize > 0
    assert word_pair_limit > candidate_samplesize
    allwords = _words(db, vocabname)  # get all words

    n_words = len(allwords)
    n_candidates = n_words if candidates is None else len(candidates)
    candidate_samplesize = min(candidate_samplesize, n_candidates)  # can only upto the population size
    # make filters to input and answer words to conduct approx, smaller optimization
    if n_words * n_candidates <= word_pair_limit:
        # within the size limit, no need for approximation
        logger.debug("No approximation needed (input words: %d, candidates: %d)", n_words, n_candidates)
        inputfilter = ""
        params1 = ()
        if candidates is None:
            answerfiler = ""
            params2 = ()
        else:
            answerfilter = "WHERE word IN ({})".format(",".join("?" * n_candidates))
            params2 = tuple(candidates)
        params = tuple(params1) + tuple(params2)
    elif n_words * candidate_samplesize <= word_pair_limit:
        # need approximation, and
        # we can reduce the problem size by sampling the answer words only
        n_candidates2 = int(word_pair_limit / n_words)  # candidate sample size
        logger.debug("Approximation with candidate sampling (input words: %d, candidates: %d -> %d)",
                     n_words, n_candidates, n_candidates2)
        answerfilter = "WHERE word IN ({})".format(",".join("?" * n_candidates2))
        params2 = random.sample(allwords if candidates is None else candidates, n_candidates2)
        inputfilter = ""
        params1 = ()
        params = tuple(params1) + tuple(params2)
    else:
        # need approximation, and need input words sampling
        n_words2 = int(word_pair_limit / candidate_samplesize)
        inputfilter = "WHERE word IN ({})".format(",".join("?" * n_words2))
        params1 = random.sample(allwords, n_words2)
        if candidate_samplesize == n_candidates:
            logger.debug("Approximation with input word sampling (input words: %d -> %d, candidates: %d)",
                         n_words, n_words2, candidate_samplesize)
            if candidates is None:
                answerfiler = ""
                params2 = ()
            else:
                answerfilter = "WHERE word IN ({})".format(",".join("?" * n_candidates))
                params2 = tuple(candidates)
        else:
            logger.debug("Approximation with input word and candidate sampling (input words: %d -> %d, candidates: %d -> %d)",
                         n_words, n_words2, n_candidates, candidate_samplesize)
            answerfilter = "WHERE word IN ({})".format(",".join("?" * candidate_samplesize))
            params2 = random.sample(allwords if candidates is None else candidates, candidate_samplesize)
        params = tuple(params1) + tuple(params2)

#    with sqlite3.connect(dbfile) as conn:
    with _connect(db) as conn:
        conn.create_function("log2", 1, math.log2)
        conn.create_function("WordleJudge", 2, wordle_judge)
        c = conn.cursor()

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
        out = {row[0]: row + (1 if candidate_set is None else int(row[0] in candidate_set),) for row in c}
    # we pad random evals is there are insufficient rows
    # for padded words, we assign the worst possible values for max_n, mean_n, mean_entropy
    defaults = (n_candidates, n_candidates, math.log2(n_candidates))
    for w in allwords:
        if len(out) >= top_k:
            break
        if w in out:
            continue
        out[w] = (w,) + defaults + (int(w in candidate_set),)
    out = [WordEvaluation(*row) for row in out.values()]
    out.sort(key=lambda row: (getattr(row, criterion), -row.is_candidate))
    out = out[:top_k]
    return out

def _vocabnames(db: str or sqlite3.Connection)-> list:
#    with sqlite3.connect(dbfile) as conn:
    with _connect(db) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master")
        tables = [row[0] for row in c]
        #print(tables)
        t = [t[:-13] for t in tables if t.endswith("_words_approx")]
    return t

def _words(db: str or sqlite3.Connection, vocabname: str)-> list:
#    with sqlite3.connect(dbfile) as conn:
    with _connect(db) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM "{name}_words_approx"'.format(name=vocabname))
        words = [row[0] for row in c]
    return words

def _choose_word_with_weight(db: str or sqlite3.Connection, vocabname: str)-> str:    
    with _connect(db) as conn:
        sqlite3.enable_callback_tracebacks(True)
        conn.create_function("log", 1, math.log)
        c = conn.cursor()
        # The query below uses the fact that
        # Prob{ u_i^(1/w_i) > u_j^(1/w_j) } = w_i / (w_i + w_j),
        #   where u_i, u_j ~ uniform(0, 1).
        #
        # References: 
        #   https://utopia.duth.gr/~pefraimi/research/data/2007EncOfAlg.pdf
        #   https://stackoverflow.com/questions/1398113/how-to-select-one-row-randomly-taking-into-account-a-weight
        # 
        # On SQLite, random() generate an integer from [-9223372036854775808, +9223372036854775808]
        # Remove the sign and take mod n to make them roughly uniform on [0, n-1]
        # Then plus 0.5 to avoid zero, i.e. uniform on [0.5, ..., n-0.5]
        # Dividing by n, uniform on [0.5/n, ... 1-0.5/n]
        # With n large enough, the retult is roughly uniform on (0, 1)
        q = """
        SELECT
          word,
          -log((abs(random()) % 1000000 + 0.5) / 1000000.0) / weight  AS priority
        FROM
          "{name}_words_approx"
        WHERE
          weight > 0
        ORDER BY priority
        LIMIT 1
        """.format(name=vocabname)
        c.execute(q)
        ans = c.fetchall()
    #print(ans)
    return ans[0][0]

def _weight_defined(db: str or sqlite3.Connection, vocabname: str)-> bool:
    with _connect(db) as conn:
        c = conn.cursor()
        # check the existing column
        c.execute('SELECT * FROM "{name}_words_approx" LIMIT 1'.format(name=vocabname))
        for col in c.description:
            if col[0].lower() == "weight":
                return True
    return False

class WordleAIApprox(WordleAISQLite):
    """
    Wordle AI with SQLite backend without precomputation.

    By omitting precomputation, this class computes approximation results
    faster and with smaller storage.

    Vocab information is stored in {vocabname}_words

    Args:
        vocabname (str):
            Name of vocaburary
        words (str or list or dict): 
            If str, the path to a vocabulary file
            If list, the list of words
            If dict, mapping from word to the weight
            Can be omitted if the vocabname is already in the database and resetup=False
        dbfile (str):
            SQLite database file
            If not supplied, use environment variable `WORDLEAISQL_DBFILE` if exists,
            otherwise './wordleai.db' in the current directory is used
        inmemory (bool):
            If true, ignore `dbfile` and use ':memory:' instead, so the in-memory database is used.

        word_pair_limit (int):
            Limit of the len(input_words) * len(candidates) to compute the evaluation.
            The larger, the more accurate approximation.
        candidate_samplesize (int):
            Sample size for the answer words for approximation.

        decision_metric (str):
            The criteria to pick a word
            Either 'max_n', 'mean_n', of 'mean_entropy'
        candidate_weight (float):
            The weight added to the answer candidate word when picking a word
        strength (float):
            AI strength in [0, 10]

        resetup (bool):
            Setup again if the vocabname already exists
    """
    def __init__(self, vocabname: str, words: list or str=None, dbfile: str=None, inmemory: bool=False,
                 word_pair_limit: int=500000, candidate_samplesize: int=500,
                 decision_metric: str="mean_entropy", candidate_weight: float=0.3, strength: float=6,
                 resetup: bool=False, **kwargs):
        if inmemory:
            dbfile = ":memory:"  # ignore dbfile supplied and use in-memory database
        else:
            if dbfile is None:
                dbfile = os.environ.get("WORDLEAISQL_DBFILE")
                if dbfile is None:
                    dbfile = "./wordleai.db"
            os.makedirs(os.path.dirname(os.path.abspath(dbfile)), exist_ok=True)
        self.dbfile = dbfile
        self.db = sqlite3.connect(self.dbfile)
        assert word_pair_limit > candidate_samplesize
        assert candidate_samplesize > 0
        self.word_pair_limit = word_pair_limit
        self.candidate_samplesize = candidate_samplesize
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
            _words = (
                words if isinstance(words, dict) else
                {w:1.0 for w in words} if isinstance(words, list) else
                _read_vocabfile(words) if isinstance(words, str) else
                None
            )
            if _words is None:
                raise TypeError("Unsupported type 'words': '{}'".format(type(words)))
            logger.info("Setup tables for vocabname '%s'", vocabname)
            _setup(db=self.db, vocabname=vocabname, words=words)
        # else:
        #     _ensure_word_weight_column(dbfile, vocabname)  # make sure previously created words table has the weight column

        self._info = []                  # infomation of the judge results
        self._nonanswer_words = set([])  # words that cannot become an answer
        #self.set_candidates()

    def __del__(self):
        try:
            self.db.close()
            logger.debug("Database connection closed")
        except Exception as e:
            logger.warning("Failed to close the database connection: '%s'".format(e))

    @property
    def name(self)-> str:
        return "Wordle AI (SQLite backend, approx)"

    @property
    def vocabnames(self)-> list:
        """Available vocab names"""
        #return _vocabnames(self.dbfile)
        return _vocabnames(self.db)
    
    @property
    def words(self)-> list:
        """All words that can be inputted"""
        #return _words(self.dbfile, self.vocabname)
        return _words(self.db, self.vocabname)

    def evaluate(self, top_k: int=20, criterion: str="mean_entropy")-> list:
        """
        Evaluate input words and return the top ones in accordance with the given criterion
        """
        # return _evaluate(self.dbfile, self.vocabname, top_k=top_k, criterion=criterion, candidates=self.candidates,
        #                  word_pair_limit=self.word_pair_limit, candidate_samplesize=self.candidate_samplesize)
        return _evaluate(self.db, self.vocabname, top_k=top_k, criterion=criterion, candidates=self.candidates,
                         word_pair_limit=self.word_pair_limit, candidate_samplesize=self.candidate_samplesize)

    def choose_answer_word(self, weighted: bool=True)-> str:
        """Randomly choose an answer word in accordance with the given weight"""
        if not weighted:
            return random.choice(self.words)
            
        if not _weight_defined(self.db, self.vocabname):
            print("Word weight is not defined. Please call `WordleAIApprox` with `resetup=True` next time", file=sys.stderr)
            return random.choice(self.words)
        return _choose_word_with_weight(self.db, self.vocabname)
