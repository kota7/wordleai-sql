# -*- coding: utf-8 -*-

import unittest
import os
import math
from tempfile import TemporaryDirectory

from wordleaisql.approx import WordleAIApprox

class TestApprox(unittest.TestCase):
    def test_sqlite(self):
        words = ["sheep", "shoes", "stage", "store", "style"]
        with TemporaryDirectory() as d:
            dbfile = os.path.join(d, "test.db")
            ai = WordleAIApprox("test", words, dbfile=dbfile)

            # words must equal
            self.assertEqual(set(words), set(ai.words))

            # initial candidates must equal all words
            #ai.set_candidates()
            ai.clear_info()
            self.assertEqual(set(words), set(ai.candidates))

            # initial result must be...
            # input_word	max_n	avg_n	avg_log2n is_candidate
            # --------------------------------------------------------------------
            #   input_word         max_n        mean_n  mean_entropy  is_candidate
            # --------------------------------------------------------------------
            #        shoes             2           1.4         0.400             1
            #        store             2           1.4         0.400             1
            #        stage             2           1.8         0.800             1
            #        style             2           1.8         0.800             1
            #        sheep             3           2.2         0.951             1
            # --------------------------------------------------------------------
            results = ai.evaluate(criterion="max_n")
            expected = {
               "sheep": (3, 2.2, 0.951, 1)
              ,"shoes": (2, 1.4, 0.400, 1)
              ,"stage": (2, 1.8, 0.800, 1)
              ,"store": (2, 1.4, 0.400, 1)
              ,"style": (2, 1.8, 0.800, 1)
            }
            for row in results:
                self.assertEqual(len(row), 5)
                ans = expected[row[0]]
                for a, b in zip(row[1:], ans):
                    self.assertAlmostEqual(a, b, msg="Error at initial evaluation of '{}'".format(row[0]), places=3)
            
            # update result
            ai.update("sheep", "20100")
            self.assertEqual(set(["stage", "store", "style"]), set(ai.candidates))

            # --------------------------------------------------------------------
            #   input_word         max_n        mean_n  mean_entropy  is_candidate
            # --------------------------------------------------------------------
            #        stage             2           1.7         0.667             1
            #        store             2           1.7         0.667             1
            #        style             2           1.7         0.667             1
            #        shoes             2           1.7         0.667             0
            #        sheep             3           3.0         1.585             0
            # --------------------------------------------------------------------
            results = ai.evaluate(criterion="max_n")
            expected = {
               "sheep": (3, 3.000, 1.585, 0)
              ,"shoes": (2, 1.667, 0.667, 0)
              ,"stage": (2, 1.667, 0.667, 1)
              ,"store": (2, 1.667, 0.667, 1)
              ,"style": (2, 1.667, 0.667, 1)
            }
            for row in results:
                self.assertEqual(len(row), 5)
                ans = expected[row[0]]
                for a, b in zip(row[1:], ans):
                    self.assertAlmostEqual(a, b, msg="Error at the second evaluation of '{}'".format(row[0]), places=3)
            

            # ai should pick a word
            word = ai.pick_word()
            self.assertEqual(type(word), str)
            self.assertTrue(word in ai.words)

    def test_inmemory(self):
        words = ["sheep", "shoes", "stage", "store", "style"]
        ai = WordleAIApprox("test", words, inmemory=True)

        self.assertEqual(ai.dbfile, ":memory:")
        self.assertFalse(os.path.isfile(ai.dbfile), msg="'{}' must not be a file".format(ai.dbfile))

        # words must equal
        self.assertEqual(set(words), set(ai.words))

        # initial candidates must equal all words
        #ai.set_candidates()
        ai.clear_info()
        self.assertEqual(set(words), set(ai.candidates))

        # initial result must be...
        # input_word	max_n	avg_n	avg_log2n is_candidate
        # --------------------------------------------------------------------
        #   input_word         max_n        mean_n  mean_entropy  is_candidate
        # --------------------------------------------------------------------
        #        shoes             2           1.4         0.400             1
        #        store             2           1.4         0.400             1
        #        stage             2           1.8         0.800             1
        #        style             2           1.8         0.800             1
        #        sheep             3           2.2         0.951             1
        # --------------------------------------------------------------------
        results = ai.evaluate(criterion="max_n")
        expected = {
            "sheep": (3, 2.2, 0.951, 1)
            ,"shoes": (2, 1.4, 0.400, 1)
            ,"stage": (2, 1.8, 0.800, 1)
            ,"store": (2, 1.4, 0.400, 1)
            ,"style": (2, 1.8, 0.800, 1)
        }
        for row in results:
            self.assertEqual(len(row), 5)
            ans = expected[row[0]]
            for a, b in zip(row[1:], ans):
                self.assertAlmostEqual(a, b, msg="Error at initial evaluation of '{}'".format(row[0]), places=3)
        
        # update result
        ai.update("sheep", "20100")
        self.assertEqual(set(["stage", "store", "style"]), set(ai.candidates))

        # --------------------------------------------------------------------
        #   input_word         max_n        mean_n  mean_entropy  is_candidate
        # --------------------------------------------------------------------
        #        stage             2           1.7         0.667             1
        #        store             2           1.7         0.667             1
        #        style             2           1.7         0.667             1
        #        shoes             2           1.7         0.667             0
        #        sheep             3           3.0         1.585             0
        # --------------------------------------------------------------------
        results = ai.evaluate(criterion="max_n")
        expected = {
            "sheep": (3, 3.000, 1.585, 0)
            ,"shoes": (2, 1.667, 0.667, 0)
            ,"stage": (2, 1.667, 0.667, 1)
            ,"store": (2, 1.667, 0.667, 1)
            ,"style": (2, 1.667, 0.667, 1)
        }
        for row in results:
            self.assertEqual(len(row), 5)
            ans = expected[row[0]]
            for a, b in zip(row[1:], ans):
                self.assertAlmostEqual(a, b, msg="Error at the second evaluation of '{}'".format(row[0]), places=3)
        

        # ai should pick a word
        word = ai.pick_word()
        self.assertEqual(type(word), str)
        self.assertTrue(word in ai.words)



    def test_words_omit(self):
        # we must supply words for new vocab
        with TemporaryDirectory() as d:
            def _create_ai(dbfile, words):
                ai = WordleAIApprox("test", words, db=dbfile)
                return True
            dbfile = os.path.join(d, "test.db")
            self.assertRaises(Exception, _create_ai, dbfile, None, msg="new vocab requires word")  # need words for new vocab
            self.assertTrue(_create_ai(dbfile, ["aaa", "bbb", "acb"]))  # words supplied
            self.assertTrue(_create_ai(dbfile, None), msg="words can be omitted if vocab already exists")  # okay because vocab already exists

    def test_dbfile(self):
        # delete first
        envname = "WORDLEAISQL_DBFILE"
        envval = os.environ.get(envname)
        if envval is not None:
            del os.environ[envname]

        with TemporaryDirectory() as d:
            curdir = os.getcwd()
            try:
                os.chdir(d)
                ai = WordleAIApprox("test", ["12", "31", "50"], dbfile=None)
                self.assertEqual(os.path.abspath(ai.dbfile), os.path.abspath("./wordleai.db"), msg="dbfile in current dir")
            finally:
                os.chdir(curdir)

        with TemporaryDirectory() as d:
            dbfile = os.path.join(d, "test.db")
            os.environ[envname] = dbfile
            ai = WordleAIApprox("test", ["12", "31", "50"], dbfile=None)
            self.assertEqual(os.path.abspath(ai.dbfile), os.path.abspath(dbfile), msg="dbfile from envvar")  # envvar

            dbfile2 = os.path.join(d, "test2.db")
            ai = WordleAIApprox("test", ["12", "31", "50"], dbfile=dbfile2)
            self.assertEqual(os.path.abspath(ai.dbfile), os.path.abspath(dbfile2), msg="dbfile explicit")  # specific var
        if envval is not None:
            os.environ[envname] = envval

    def test_invalid_words(self):
        def _create_ai(words):
            with TemporaryDirectory() as d:
                dbfile = os.path.join(d, "test.db")
                ai = WordleAIApprox("test", words, dbfile=dbfile)
            return True
        self.assertRaises(Exception, _create_ai, ["sheep", "shoes", "stage", "store", "style", "superb"])
        self.assertTrue(_create_ai(["sheep", "shoes", "stage", "store", "style"]))
        self.assertRaises(Exception, _create_ai, ["松竹梅", "大中小", "甲乙丙丁"])
        self.assertTrue(_create_ai(["松竹梅", "大中小"]))
        self.assertRaises(Exception, _create_ai, ["3.1415", "2.7182", "1.23456"])
        self.assertTrue(_create_ai(["12345", "67890"]))

    def test_approx(self):
        words = ["sheep", "shoes", "stage", "store", "style"]
        with TemporaryDirectory() as d:
            dbfile = os.path.join(d, "test.db")
            from wordleaisql.utils import show_word_evaluations
            # no need for filter
            ai = WordleAIApprox("test", words, dbfile=dbfile, word_pair_limit=100, candidate_samplesize=10)
            res = ai.evaluate(criterion="mean_entropy")
            show_word_evaluations(res)

            # filter candidates
            ai = WordleAIApprox("test", words, dbfile=dbfile, word_pair_limit=10, candidate_samplesize=2)
            res = ai.evaluate(criterion="mean_entropy")
            show_word_evaluations(res)
            # only answer words are filtered, so there should be some improvement for all rows in the candidate size
            n_candidates = len(words)
            for row in res:
                self.assertTrue(row.max_n < n_candidates, msg=str(row))
                self.assertTrue(row.mean_n < n_candidates, msg=str(row))
                self.assertTrue(row.mean_entropy < math.log2(n_candidates), msg=str(row))

            # filter inputs
            ai = WordleAIApprox("test", words, dbfile=dbfile, word_pair_limit=10, candidate_samplesize=3)
            res = ai.evaluate(criterion="mean_entropy")
            show_word_evaluations(res)
            # answer sample 3, word sample 3, so there should be 2 words not evaluated
            n_candidates = len(words)
            n_excluded = sum(row.max_n == n_candidates for row in res)
            self.assertEqual(n_excluded, 2, msg="max_n")
            n_excluded = sum(row.mean_n == n_candidates for row in res)
            self.assertEqual(n_excluded, 2, msg="mean_n")
            n_excluded = sum(row.mean_entropy == math.log2(n_candidates) for row in res)
            self.assertEqual(n_excluded, 2, msg="mean_entropy")

            # for debugging, print eval result
            # assert False