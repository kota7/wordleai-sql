# -*- coding: utf-8 -*-

import unittest
import os
from tempfile import TemporaryDirectory

from wordleaisql.utils import wordle_judge, decode_judgement

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