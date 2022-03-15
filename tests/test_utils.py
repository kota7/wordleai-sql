# -*- coding: utf-8 -*-

import unittest
import os
from tempfile import TemporaryDirectory

from wordleaisql.utils import wordle_judge, decode_judgement, _read_vocabfile

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
    
    def test_reader(self):
        with TemporaryDirectory() as d:
            words = ["foo", "bar", "buz"]
            data = "\n".join(words)
            print(data)
            filename = os.path.join(d, "test.txt")
            with open(filename, "wt") as f:
                f.write(data)
            x = _read_vocabfile(filename)
            for w in words:
                self.assertEqual(x[w], x["foo"], "Default weight must be constant, but {}".format(x))

            words = {"foo": 1, "bar": 2, "buz": 3}
            data = "\n".join("{} {}".format(a, b) for a, b in words.items())
            print(data)
            filename = os.path.join(d, "test.txt")
            with open(filename, "wt") as f:
                f.write(data)
            x = _read_vocabfile(filename)
            for w in words:
                self.assertEqual(x[w], words[w], "Failed to read a file with probs: {}".format(x))
