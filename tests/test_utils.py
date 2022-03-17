# -*- coding: utf-8 -*-

import unittest
import os
from tempfile import TemporaryDirectory

from wordleaisql.utils import wordle_judge, decode_judgement, _read_vocabfile, default_wordle_vocab

class TestUtils(unittest.TestCase):
    def test_judge(self):
        cases = [
           ("tacit", "state", "11001")
          ,("smile", "funny", "00000")
          ,("aland", "ahead", "20102")
          ,("error", "peter", "10002")
          ,("一日一善", "一朝一夕", "2020")
        ]
        for c in cases:
            r = wordle_judge(c[0], c[1])
            r = decode_judgement(r)
            r = int(r)
            self.assertEqual(r, int(c[2]), msg="Judge error for {}".format(c))

    def test_default_vocab(self):
        x = default_wordle_vocab()  # okay if this works with no error
        #raise

    def test_reader(self):
        with TemporaryDirectory() as d:
            words = ["foo", "bar", "buz"]
            data = "\n".join(words)
            filename = os.path.join(d, "test.txt")
            with open(filename, "wt") as f:
                f.write(data)
            x = _read_vocabfile(filename)
            for w in words:
                self.assertEqual(x[w], x["foo"], "Default weight must be constant, but {} with data '{}'".format(x, data))

            words = {"foo": 1, "bar": 2, "buz": 3}
            data = "\n".join("{} {}".format(a, b) for a, b in words.items())
            filename = os.path.join(d, "test2.txt")
            with open(filename, "wt") as f:
                f.write(data)
            x = _read_vocabfile(filename)
            for w in words:
                self.assertEqual(x[w], words[w], "Failed to read a file with probs: {} with data '{}'".format(x, data))
            
            def _read_test(words):
                data = "\n".join("{} {}".format(a, b) for a, b in words.items())
                filename = os.path.join(d, "test2.txt")
                with open(filename, "wt") as f:
                    f.write(data)
                x = _read_vocabfile(filename)
            self.assertRaises(Exception, _read_test, {"foo": 0, "bar": 0.0, "buz": 0})
            self.assertRaises(Exception, _read_test, {"foo": 0, "bar": 0, "buz": -1})
            _read_test({"foo": 1, "bar": 0, "buz": -1})  # this is okay because -1 becomes 0

