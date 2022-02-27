# -*- coding: utf-8 -*-

import os
import sys
from collections import Counter, namedtuple
from contextlib import contextmanager
from datetime import datetime

def wordle_judge(input_word: str, answer_word: str)-> int:
    """
    Judge input word based on the wordle rule
    
    We assume input_word and answer_word are of the same length (but no check is conducted)

    Judge results are defined as a sequence of {0, 1, 2}, where
      2: exact, 1: partial, 0: none
    Return value is the base-10 integer value that represents this result interpreted as an integer of base 3.

    e.g. 22001 --> 2 * 3^4 + 2 * 3*3 + 0 * 3^2 + 0 * 3^2 + 1 * 3^0 = 181
    """
    
    exactmatch = [a==b for a, b in zip(input_word, answer_word)]
    lettercount = Counter(b for b, m in zip(answer_word, exactmatch) if not m)
    partialmatch = [False] * len(input_word)
    for i, (a, m) in enumerate(zip(input_word, exactmatch)):
        if m: continue
        if lettercount.get(a, 0) > 0:
            lettercount[a] -= 1
            partialmatch[i] = True
    out = 0
    power = 1
    for x, y in zip(reversed(exactmatch), reversed(partialmatch)):
        if x:
            out += power*2
        elif y:
            out += power
        power *= 3
    return out

def decode_judgement(number: int or str)-> int:
    # convert to human-friendly integer
    number = int(number)
    out = 0
    power = 1
    while number > 0:
        out += power*(number % 3)
        number = int(number / 3)
        power *= 10
    return out

def encode_judgement(number: int)-> int:
    # convert to expression system 
    if type(number) != int:
        number = int(number)
    out = 0
    power = 1
    while number > 0:
        out += power*(number % 10)
        number = int(number / 10)
        power *= 3
    return out


# Evaluation of input word
WordEvaluation = namedtuple("WordEvaluation", "input_word max_n mean_n mean_entropy is_candidate")
def show_word_evaluations(x: list):
    # evaluation result is a list of dict, with the same keys repeated
    if len(x) == 0:
        print("No data.")
        return
    keys = ("input_word", "max_n", "mean_n", "mean_entropy", "is_candidate")
    rowfmt = "%12s  %12s  %12s  %12s  %12s"
    fmt = "%12s  %12d  %12.1f  %12.3f  %12d"

    print("-" * (12*5 + 4*2))
    print(rowfmt % keys)
    print("-" * (12*5 + 4*2))
    for row in x:
        print(fmt % row)
    print("-" * (12*5 + 4*2))


def _package_data_file(filepath: str)-> str:
    try:
        import importlib.resources
        return str(importlib.resources.Path("wordleaisql") / filepath)
    except:
        import importlib_resources
        return str(importlib_resources.files("wordleaisql") / filepath)
    raise RuntimeError("File '{}' not found".format(filepath))

def _read_vocabfile(filepath: str)-> set:
    assert os.path.isfile(filepath), "'{}' does not exist".format(filepath)
    with open(filepath) as f:
        words = [line.strip() for line in f]
        # remove empty strings, just in case
        words = [w for w in words if len(w) > 0]
    
    return set(words)

def default_wordle_vocab()-> set:
    vocabfile =  _package_data_file("wordle-vocab.txt")
    words = _read_vocabfile(vocabfile)
    return words

@contextmanager
def _timereport(taskname: str="task", datetimefmt: str="%Y-%m-%d %H:%M:%S"):
    t1 = datetime.now()
    print("Start %s (%s)" % (taskname, t1.strftime(datetimefmt)), file=sys.stderr)
    yield
    t2 = datetime.now()
    print("End %s (%s, elapsed: %s)" % (taskname, t2.strftime(datetimefmt), t2-t1), file=sys.stderr)
