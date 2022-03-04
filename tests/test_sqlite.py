# -*- coding: utf-8 -*-

import unittest
import os
from tempfile import TemporaryDirectory

from wordleaisql.sqlite import WordleAISQLite

class TestSQLite(unittest.TestCase):
    def test_sqlite(self):
        words = ["sheep", "shoes", "stage", "store", "style"]
        with TemporaryDirectory() as d:
            dbfile = os.path.join(d, "test.db")
            ai = WordleAISQLite("test", words, dbfile=dbfile)

            # words must equal
            self.assertEqual(set(words), set(ai.words))

            # initial candidates must equal all words
            ai.set_candidates()            
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

    def test_invalid(self):
        def _create_ai(words):
            with TemporaryDirectory() as d:
                dbfile = os.path.join(d, "test.db")
                ai = WordleAISQLite("test", words, dbfile=dbfile)
            return True
        self.assertRaises(Exception, _create_ai, ["sheep", "shoes", "stage", "store", "style", "superb"])
        self.assertTrue(_create_ai(["sheep", "shoes", "stage", "store", "style"]))
        self.assertRaises(Exception, _create_ai, ["松竹梅", "大中小", "甲乙丙丁"])
        self.assertTrue(_create_ai(["松竹梅", "大中小"]))
        self.assertRaises(Exception, _create_ai, ["3.1415", "2.7182", "1.23456"])
        self.assertTrue(_create_ai(["12345", "67890"]))
