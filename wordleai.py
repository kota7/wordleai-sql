#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Wordle AI with SQLite backend.
"""

import itertools
import math
import os
import re
import sqlite3
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import Counter
from datetime import datetime
from tqdm import tqdm


def wordle_response(input_word: str, answer_word: str)-> int:
    assert len(input_word) == len(answer_word), "Word length mismatch ([] vs {})".format(len(input_word), len(answer_word))
    exactmatch = [a==b for a, b in zip(input_word, answer_word)]
    lettercount = Counter(b for b, m in zip(answer_word, exactmatch) if not m)
    partialmatch = [False] * len(input_word)
    for i, (a, m) in enumerate(zip(input_word, exactmatch)):
        if m: continue
        if lettercount.get(a, 0) > 0:
            lettercount[a] -= 1
            partialmatch[i] = True
    # Define the response as an integer of base 3
    #   with 2: exact, 1: partial, 0: none
    # To reduce the variable size, we store the integer of base 10
    out = 0
    power = 1
    for x, y in zip(reversed(exactmatch), reversed(partialmatch)):
        if x:
            out += power*2
        elif y:
            out += power
        power *= 3
    return out

def decode_response(number: int)-> int:
    # convert to human-friendly integer 
    out = 0
    power = 1
    while number > 0:
        out += power*(number % 3)
        number = int(number / 3)
        power *= 10
    return out

def encode_response(number: int)-> int:
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


def create_database(dbfile: str, words: list):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS words")
        c.execute("CREATE TABLE words (word TEXT PRIMARY KEY)")
        params = [(w,) for w in words]
        c.executemany("INSERT INTO words VALUES (?)", params)                
        conn.commit()

def compute_all_responses(dbfile: str):
    # ToDo. This part take very long time (about 20-30 minutes)
    #       Maybe cythonize this part to enhance the computation.
    def generate_responses(words):
        total = len(words)**2
        nchar = len(str(total))
        fmt = "\r%{nchar}d / %{nchar}d %5.1f%% |%-50s| %s remaining".format(nchar=nchar)
        t1 = datetime.now()
        for input_word, answer_word in tqdm(itertools.product(words, words), total=total):
            # pcent = 100.0 * (i+1) / total
            # bar = "#" * int(pcent / 2)
            # remain = str((datetime.now() - t1) / i * (total - i)) if i > 0 else "???"
            # remain = remain[:10]
            # print(fmt % (i+1, total, pcent, bar, remain), end="", file=sys.stderr)

            response = wordle_response(input_word, answer_word)
            yield (input_word, answer_word, response)
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS responses")        
        c.execute("CREATE TABLE responses (input_word TEXT, answer_word TEXT, response INT)")
        c.execute("SELECT word FROM words")
        words = [row[0] for row in c]
        t1 = datetime.now()
        print("Start computing responses (%s)" % t1, file=sys.stderr)
        q = "INSERT INTO responses VALUES (?,?,?)"
        params = generate_responses(words)
        c.executemany(q, params)
        t2 = datetime.now()
        print("End computing responses (%s, elapsed: %s)" % (t2, t2-t1), file=sys.stderr)
        
        t1 = datetime.now()
        print("Start creating index (%s)" % t1, file=sys.stderr)
        c.execute("CREATE INDEX responses_idx ON responses (input_word, response)")
        c.execute("CREATE INDEX responses_idx2 ON responses (answer_word)")
        t2 = datetime.now()
        print("End creating index (%s, elapsed: %s)" % (t2, t2-t1), file=sys.stderr)
        conn.commit()

    # with sqlite3.connect(dbfile) as conn:
    #     conn.create_function("wordle_response", 2, wordle_response)
    #     c = conn.cursor()
        
    #     c.execute("DROP TABLE IF EXISTS responses")        
    #     q = """
    #     SELECT
    #       a.word AS input_word,
    #       b.word AS answer_word,
    #       wordle_response(a.word, b.word) AS response
    #     FROM
    #       words AS a, words AS b
    #     """
    #     t1 = datetime.now()
    #     print("Start computing responses (%s)" % t1, file=sys.stderr)
    #     c.execute("CREATE TABLE responses AS {}".format(q))
    #     t2 = datetime.now()
    #     print("End computing responses (%s, elapsed: %s)" % (t2, t2-t1), file=sys.stderr)
        
    #     t1 = datetime.now()
    #     print("Start creating index (%s)" % t1, file=sys.stderr)
    #     c.execute("CREATE INDEX responses_idx ON responses (input_word, response)")
    #     c.execute("CREATE INDEX responses_idx2 ON responses (answer_word)")
    #     t2 = datetime.now()
    #     print("End creating index (%s, elapsed: %s)" % (t2, t2-t1), file=sys.stderr)
    #     conn.commit()

# ToDo. make candidate table session specific.
def init_candidates(dbfile: str):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS candidates")
        c.execute("CREATE TABLE candidates AS SELECT word FROM words")
        conn.commit()

def evaluate_candidates(dbfile: str):
    with sqlite3.connect(dbfile) as conn:
        conn.create_function("log2", 1, math.log2)
        c = conn.cursor()

        c.execute("SELECT count(*) FROM candidates")
        n_candidates = c.fetchone()[0]
        c.execute("SELECT count(*) FROM words")
        n_words = c.fetchone()[0]
        answerfilter = "" if n_words == n_candidates else "WHERE answer_word IN (SELECT word FROM candidates)"

        q = """
        with tmp AS (
          SELECT
            input_word,
            response,
            count(*) AS n,
            log2(count(*)) AS entropy
          FROM
            responses
          {answerfilter}
          GROUP BY
            input_word, response
        ),
        tmp2 AS (
          SELECT
            input_word,
            max(n) AS max_n,
            1.0 * sum(n*n) / sum(n) AS mean_n,
            sum(n*entropy) / sum(n) AS mean_entropy
          FROM
            tmp
          GROUP BY
            input_word
        )
        SELECT
          t.*,
          coalesce(c.is_candidate, 0) AS is_candidate
        FROM
          tmp2 AS t
        LEFT JOIN (SELECT word, 1 AS is_candidate FROM candidates) AS c
          ON t.input_word = c.word
        """.format(answerfilter=answerfilter)
        t1 = datetime.now()
        print("Start evaluating candidates (%s)" % t1, file=sys.stderr)
        c.execute(q)
        t2 = datetime.now()
        print("End evaluating candidates (%s, elapsed: %s)" % (t2, t2-t1), file=sys.stderr)
        names = [c[0] for c in c.description]
        out = [{name: value for name, value in zip(names, row)} for row in c]
    return out

def update_candidate(dbfile: str, input_word: str, response: str):    
    encoded = encode_response(int(response))
    with sqlite3.connect(dbfile) as conn:
        q = """
        DELETE FROM candidates WHERE word NOT IN (
          SELECT
            answer_word
          FROM
            responses
          WHERE
            input_word = ? AND response = ?
        )
        """
        param = (input_word, encoded)
        c = conn.cursor()        
        c.execute(q, param)
        conn.commit()

def get_candidates(dbfile: str, n: int=30):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM candidates")
        count = c.fetchone()[0]
        c.execute("SELECT word FROM candidates LIMIT {}".format(n))
        candidates = [row[0] for row in c.fetchall()]

    return count, candidates


def read_vocabfile(filepath: str):
    assert os.path.isfile(filepath), "'{}' does not exist".format(filepath)
    with open(filepath) as f:
        words = [line.strip() for line in f]
        # remove empty strings, just in case
        words = [w for w in words if len(w) > 0]
    return words

class WordleAISQLite:
    def __init__(self, dbfile: str, words: list or str=None, recompute: bool=False):
        self.dbfile = dbfile
        if not os.path.isfile(dbfile) or recompute:
            if type(words) == str:
                words = read_vocabfile(words)
            # words must be unique
            words = list(set(words))
            print("Start setting up the database, this would take a while (typically around 30 minutes)")
            create_database(dbfile, words)
            compute_all_responses(dbfile)
            print("End setting up the database")

    def initialize(self):
        init_candidates(self.dbfile)

    def evaluate(self, top_k: int=20, criterion: str="mean_entropy"):
        res = evaluate_candidates(self.dbfile)
        # sort by the given criterion
        # if that criterion is equal, then we prioritize candidate words
        res.sort(key=lambda row: (row[criterion], -row["is_candidate"]))
        # return only top_k
        return res[:top_k]

    def update(self, input_word: str, result: str or int):
        update_candidate(self.dbfile, input_word, result)

    def remaining_candidates(self, n: int=10)-> bool:
        # return True if zero or one candidate left
        count, candidates = get_candidates(self.dbfile, n=n)
        if count > n:
            candidates.append("...")

        if count > 1:
            print("%d remaining candidates: %s" % (count, candidates))
            return False
        elif count==1:
            print("'%s' should be the answer!" % candidates[0])
            return True
        else:
            print("There is no candidate words consistent with the information...")
            return True


def receive_user_command():
    while True:
        message = [
          "",
          "Type:",
          "  '[s]uggest <criterion>'     to let AI suggest a word",
          "  '[u]pdate <word> <result>'  to provide new information",
          "  '[e]xit'                    to finish the session",
          "", 
          "where",
          "  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'",
          "  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)",
          "",
          "> "
        ]
        ans = input("\n".join(message))
        if len(ans) <= 0:
            continue

        if ans[0] == "s":
            if len(ans) > 1:
                criterion = ans[1]
                if criterion not in ("max_n", "mean_n", "mean_entropy"):
                    print("Invalid <criterion> ('%s' is given)" % criterion)
                    continue
                return ["s", criterion]
            else:
                return ["s"]
        elif ans[0] == "u":
            ans = re.sub(r"\s+", " ", ans)
            ans = ans.split(" ")
            if len(ans) < 3:
                continue
            word, result = ans[1], ans[2]
            if not all(r in "012" for r in result):
                print("'%s' is invalid <result>")
                continue
            if len(word) < len(result):
                print("Word and result length mismatch")
                continue
            return ["u", word, result]
        elif ans[0] == "e":
            return ["e"]

def print_eval_result(x: list):
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
        values = tuple([row.get(k, "") for k in keys])
        print(fmt % values)
    print("-" * (12*5 + 4*2))


def main():
    parser = ArgumentParser(description="Wordle AI with SQLite backend", formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("--dbfile", type=str, default="wordle-ai.db", help="SQLite database file")
    parser.add_argument("--vocabfile", type=str, default="vocab.txt", help="Text file containing words")
    parser.add_argument("--default_criterion", type=str, default="mean_entropy",
                        choices=("max_n", "mean_n", "mean_entropy"), help="Criterion to suggest word")
    parser.add_argument("--num_suggest", type=int, default=20, help="Number of word suggestions")
    parser.add_argument("--recompute", action="store_true", help="Force recompute for the database setup")
    args = parser.parse_args()

    print("")
    print("Hello! This is Wordle AI with SQLite backend.")
    print("")

    ai = WordleAISQLite(args.dbfile, words=args.vocabfile, recompute=args.recompute)
    ai.initialize()

    while True:
        if ai.remaining_candidates():
            break

        ans = receive_user_command()
        if ans[0] == "s":
            criterion = args.default_criterion if len(ans) < 2 else ans[1]
            res = ai.evaluate(top_k=args.num_suggest, criterion=criterion)
            print("* Top %d candidates ordered by %s" % (len(res), criterion))
            print_eval_result(res)
        elif ans[0] == "u":
            ai.update(ans[1], ans[2])
        elif ans[0] == "e":
            break

    print()
    print("Thank you!")


if __name__ == "__main__":
    main()