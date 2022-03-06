# -*- coding: utf-8 -*-

import unittest
import os
from tempfile import TemporaryDirectory

from wordleaisql.base import WordleAI

class TestBase(unittest.TestCase):
    def test_base(self):
        words = ["sheep", "shoes", "stage", "store", "style"]
        ai = WordleAI("test", words)

        # words must equal
        self.assertEqual(set(words), set(ai.words))

        # initial candidates must equal all words
        #ai.set_candidates()
        ai.clear_info()
        self.assertEqual(set(words), set(ai.candidates))

        results = ai.evaluate(criterion="max_n")
        self.assertEqual(len(results), len(words))
        for row in results:
            self.assertEqual(len(row), 5)
        
        # update result
        ai.update("sheep", "20100")
        self.assertEqual(set(["stage", "store", "style"]), set(ai.candidates))

        results = ai.evaluate(criterion="max_n")
        self.assertEqual(len(results), len(words))
        for row in results:
            self.assertEqual(len(row), 5)

        # ai should pick a word
        word = ai.pick_word()
        self.assertEqual(type(word), str)
        self.assertTrue(word in ai.words)

    def test_invalid(self):
        def _create_ai(words):
            ai = WordleAI("test", words)
            return True
        self.assertRaises(Exception, _create_ai, ["sheep", "shoes", "stage", "store", "style", "superb"])
        self.assertTrue(_create_ai(["sheep", "shoes", "stage", "store", "style"]))
        self.assertRaises(Exception, _create_ai, ["松竹梅", "大中小", "甲乙丙丁"])
        self.assertTrue(_create_ai(["松竹梅", "大中小"]))
        self.assertRaises(Exception, _create_ai, ["3.1415", "2.7182", "1.23456"])
        self.assertTrue(_create_ai(["12345", "67890"]))
        