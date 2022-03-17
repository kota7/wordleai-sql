# -*- coding: utf-8 -*-

import os
import gzip
import sys
import itertools
import hashlib
import subprocess
from collections import Counter, namedtuple
from contextlib import contextmanager
from datetime import datetime
from tempfile import TemporaryDirectory
from logging import getLogger
logger = getLogger(__name__)

from tqdm import tqdm

def _dedup(x: list)-> list: 
    return list(dict.fromkeys(x))

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
        # importlib.resrouces.files is new in python 3.9
        # this is a workaround I found
        with importlib.resources.path("wordleaisql", filepath) as f:
            return str(f)
    except Exception as e:
        logger.info("Error finding package data file '%s': '%s'", filepath, e)
        import importlib_resources
        return str(importlib_resources.files("wordleaisql") / filepath)
    raise RuntimeError("File '{}' not found".format(filepath))

def _read_vocabfile(filepath: str)-> dict:
    assert os.path.isfile(filepath), "'{}' does not exist".format(filepath)
    opener = gzip.open if filepath.endswith(".gz") else open
    with opener(filepath, "rt") as f:
        out = {}
        for line in f:
            tmp = line.strip()
            if len(tmp) == 0:
                continue
            tmp = tmp.split()
            if len(tmp) == 1:
                # add weight 1
                out[tmp[0]] = 1
            else:
                v = float(tmp[1])
                if v < 0:
                    logger.warning("Negative weight is not allowed, '%s' is changed to zero", v)
                    v = 0
                out[tmp[0]] = v
    # some weight must be positive
    flg = any(p > 0 for p in out.values())
    #print(out.values())
    if not flg:
        raise ValueError("All weights are zero")
    return out

read_vocabfile = _read_vocabfile  # make open to end user

def default_vocabfile()-> str:
    return _package_data_file("wordle-vocab.txt")

def default_wordle_vocab()-> dict:
    vocabfile = default_vocabfile()
    words = _read_vocabfile(vocabfile)
    return words

@contextmanager
def _timereport(taskname: str="task", datetimefmt: str="%Y-%m-%d %H:%M:%S"):
    t1 = datetime.now()
    logger.info("Start %s (%s)", taskname, t1.strftime(datetimefmt))
    yield
    t2 = datetime.now()
    logger.info("End %s (%s, elapsed: %s)", taskname, t2.strftime(datetimefmt), t2-t1)


def _all_wordle_judges(words: list):
    total = len(words)**2
    nchar = len(str(total))
    for input_word, answer_word in tqdm(itertools.product(words, words), total=total):
        response = wordle_judge(input_word, answer_word)
        yield (input_word, answer_word, response)

def _compile_cpp(scriptfile: str, execfile: str, md5file: str, compiler: str=None, recompile: bool=False)-> bool:
    # Returns true is successful

    # we keep the md5 info of the source file to detect any changes
    # and compile the file only if the hash is not changed
    os.makedirs(os.path.dirname(execfile), exist_ok=True)
    os.makedirs(os.path.dirname(md5file), exist_ok=True)

    # compare the hash record
    if os.path.isfile(md5file):
        with open(md5file) as f:
            hash_prev = f.read()
    else:
        hash_prev = None
    h = hashlib.md5()
    with open(scriptfile, "rb") as f:
        h.update(f.read())
    hash_this = h.hexdigest()
    script_updated = (hash_this != hash_prev)
    
    if os.path.isfile(execfile) and (not script_updated) and (not recompile):
        logger.info("Compiled file ('%s') already exists and source has no update", execfile)
        return True
    else:
        # compile cpp script
        if compiler is None:
            # find a c++ compiler
            for c in ("g++", "clang++"):
                try:
                    subprocess.run([c, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    compiler = c
                    logger.info("C++ compiler detected: '%s'", compiler)
                    break
                except FileNotFoundError:
                    continue
        if compiler is None:
            logger.warning("No C++ compiler is found, so C++ enhancement is not available")
            return False

        logger.info("Compiling C++ script (%s)", scriptfile)
        try:
            subprocess.run([compiler, "-Wall", "-Werror", "-O3", "-o", execfile, scriptfile])
            with open(md5file, "w") as f:
                f.write(hash_this)
        except Exception as e:
            logger.warning("C++ compile failed, so C++ enhancement is not available")
            return False
    return True

def _prep_cpp(words: list, recompile: bool=False, compiler: str=None)-> str:
    # Returns:
    #   compiled executable path if cpp enhancement is available
    #   none otherwise

    # check if all words are ascii. otherwise the current C++ script is not applicable
    def _ascii_no_space(letter):
        if ord(letter) > 255 or ord(letter) < 1:
            return False
        return True
    for word in words:
        if not all(_ascii_no_space(letter) for letter in word):
            logger.info("Word contains non-ascii letter '%s'", word)
            return None

    scriptfile = _package_data_file("wordle-judge-all.cpp")
    #print(scriptfile)
    #execfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "wordle-all-pairs.o"))
    execfile = os.path.expanduser("~/.worldaisql/wordle-judge-all.o")
    md5file = os.path.expanduser("~/.worldaisql/wordle-all-pairs.cpp.md5sum")

    if not _compile_cpp(scriptfile, execfile, md5file, compiler=compiler, recompile=recompile):
        logger.info("C++ compile failed")
        return None
    return execfile

def _all_wordle_judges_cpp(words: list, execfile: str):
    with TemporaryDirectory() as tmpdir:
        # create input file for the c++ script
        infile = os.path.join(tmpdir, "infile.txt")
        with open(infile, "w") as f:
            f.write(str(len(words)))
            f.write(" ".join(words))

        # run c++ script to save the results as a csv file
        outfile = os.path.join(tmpdir, "outfile.txt")
        #outfile = "responses.txt"  # for temporary check for the output table
        with open(infile) as f, open(outfile, "w") as g:
            with _timereport("Computing all wordle results"):
                subprocess.run([execfile], stdin=f, stdout=g)
        
        # generate the outcomes
        with open(outfile) as f:
            total = len(words)**2
            for line in tqdm(f, total=total):
                yield line.strip().split(" ")
    
def all_wordle_judges(words: list, use_cpp: bool=True, recompile: bool=False, compiler: str=None):
    if use_cpp:
        execfile = _prep_cpp(words, recompile, compiler)
        if execfile is not None:
            return _all_wordle_judges_cpp(words, execfile)
        else:
            logger.warning("C++ enhancement is not available, pure python implementation is used instead")

    return _all_wordle_judges(words)