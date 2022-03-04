#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import random
import itertools
from datetime import datetime
from logging import basicConfig
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

from wordleaisql.base import WordleAI
from wordleaisql.utils import wordle_judge, decode_judgement, default_wordle_vocab
from wordleaisql.sqlite import WordleAISQLite

OUTDIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTDIR, exist_ok=True)
basicConfig(level=20)
DBFILE = "wordleai.db"

def _outfile(answer_word, metric):
    return os.path.join(OUTDIR, "{}_{}.json".format(answer_word, metric))

def _finished(answer_word, metric):
    return os.path.isfile(_outfile(answer_word, metric))

def simulate_one(answer_word, metric):
    random.seed(875)
    if _finished(answer_word, metric):
        return True

    if metric == "random":
        ai = WordleAI("wordle", default_wordle_vocab())
    else:
        ai = WordleAISQLite("wordle", default_wordle_vocab(), dbfile=DBFILE)

    ai.set_candidates()
    wordlen = len(answer_word)
    out = {"answer_word": answer_word, "metric": metric, "steps": []}
    step = 0
    t1 = datetime.now()
    while True:
        step += 1
        if len(ai.candidates) == 0:
            raise RuntimeError("No candidate left for ({}, {})".format(answer_word, metric))
        elif len(ai.candidates) == 1:
            input_word = ai.candidates[0]  # only one candidate left
        elif metric == "random":
            input_word = ai.pick_word()
        else:
            if step == 1:
                input_word = "tares" if metric=="mean_entropy" else "serai" if metric=="max_n" else "lares"
            else:
                res = ai.evaluate(criterion=metric)
                input_word = res[0].input_word
        
        res = wordle_judge(input_word, answer_word)
        decoded = str(decode_judgement(res)).zfill(wordlen)
        out["steps"].append((input_word, decoded))

        if decoded == "2" * wordlen:  # correct answer has been found
            out["n_steps"] = step
            t2 = datetime.now()
            out["elapsed_sec"] = (t2-t1).total_seconds()
            break
        ai.update(input_word, decoded)
    
    with open(_outfile(answer_word, metric), "w") as f:
        json.dump(out, f)
    return True


def main():
    words = default_wordle_vocab()
    ai = WordleAISQLite("wordle", words, dbfile=DBFILE)  # create database if not exists
    metrics = ("random", "max_n", "mean_n", "mean_entropy")

    # test
    #simulate_one(words[0], metrics[0])
    #simulate_one(words[0], metrics[3])
    
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(simulate_one, word, metrics) for word, metrics in itertools.product(words, metrics)]
        total = len(words) * len(metrics)
        for res in tqdm(as_completed(futures), total=total):
            pass

if __name__ == "__main__":
    main()