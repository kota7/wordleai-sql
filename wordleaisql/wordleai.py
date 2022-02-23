#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Wordle AI with SQLite backend.
"""

import hashlib
import itertools
import math
import os
import random
import re
import sqlite3
import subprocess 
import sys
import time
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from tempfile import TemporaryDirectory
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

@contextmanager
def _timereport(taskname: str="task", datetimefmt: str="%Y-%m-%d %H:%M:%S"):
    t1 = datetime.now()
    print("Start %s (%s)" % (taskname, t1.strftime(datetimefmt)), file=sys.stderr)
    yield
    t2 = datetime.now()
    print("End %s (%s, elapsed: %s)" % (taskname, t2.strftime(datetimefmt), t2-t1), file=sys.stderr)


def create_database(dbfile: str, words: list):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS words")
        c.execute("CREATE TABLE words (word TEXT PRIMARY KEY)")
        params = [(w,) for w in words]
        c.executemany("INSERT INTO words VALUES (?)", params)                
        conn.commit()

def generate_responses_python_only(words: list):
    total = len(words)**2
    nchar = len(str(total))
    fmt = "\r%{nchar}d / %{nchar}d %5.1f%% |%-50s| %s remaining".format(nchar=nchar)
    for input_word, answer_word in tqdm(itertools.product(words, words), total=total):
        response = wordle_response(input_word, answer_word)
        yield (input_word, answer_word, response)

def _package_data_file(filepath: str)-> str:
    try:
        import importlib_resources
        return str(importlib_resources.files("wordleaisql") / filepath)
    except:
        import importlib.resources
        return str(importlib.resources.files("wordleaisql") / filepath)
    raise RuntimeError("File '{}' not found".format(filepath))


def _make_enhanced_response_generator(compiler: str=None, force_recompile: bool=False):
    # script file path

    #scriptfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "wordle-all-pairs.cpp"))
    scriptfile = _package_data_file("wordle-all-pairs.cpp")
    #print(scriptfile)
    #execfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "wordle-all-pairs.o"))
    execfile = os.path.expanduser("~/.worldaisql/wordle-all-pairs.o")
    md5file = os.path.expanduser("~/.worldaisql/wordle-all-pairs.cpp.md5sum")
    # we keep the md5 info of the source file to detect any changes
    # and compile the file only if the hash is not changed
    os.makedirs(os.path.dirname(execfile), exist_ok=True)

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
    
    if os.path.isfile(execfile) and (not script_updated) and (not force_recompile):
        print("Compiled file ('%s') already exists and source has no update" % execfile, file=sys.stderr)
    else:
        # compile cpp script
        if compiler is None:
            # find a c++ compiler
            for c in ("g++", "clang++"):
                try:
                    subprocess.run([c, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    compiler = c
                    print("C++ compiler detected: '%s'" % compiler, file=sys.stderr)
                    break
                except FileNotFoundError:
                    continue
        if compiler is None:
            print("No C++ compiler is found, so C++ enhancement is not available", file=sys.stderr)
            return None
        print("Compiling C++ script (%s)" % scriptfile, file=sys.stderr)
        try:
            subprocess.run([compiler, "-Wall", "-Werror", "-O3", "-o", execfile, scriptfile])
            with open(md5file, "w") as f:
                f.write(hash_this)
        except Exception as e:
            print("C++ compile failed, so C++ enhancement is not available", file=sys.stderr)
            return None

    def generate_responses_cpp(words: list):
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
                with _timereport("precomputing all wordle results"):
                    subprocess.run([execfile], stdin=f, stdout=g)
            
            # generate the outcomes
            with open(outfile) as f:
                total = len(words)**2
                for line in tqdm(f, total=total):
                    yield line.strip().split(" ")

    return generate_responses_cpp


def compute_all_responses(dbfile: str, usecpp: bool=True, cppcompiler: str=None, force_recompile: bool=False):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("SELECT word FROM words")
        words = [row[0] for row in c]
    # check if all words are ascii and not a space character (otherwise cpp script does not work)
    def _ascii_no_space(letter):
        if ord(letter) > 255 or ord(letter) < 1:
            return False
        if re.search(r"\s", letter) is not None:
            return False
        return True
    all_ascii_no_space = True
    for word in words:
        if not all(_ascii_no_space(letter) for letter in word):
            all_ascii_no_space = False
            break

    generator = None
    if usecpp:
        if not all_ascii_no_space:
            print("C++ enhancement is not available for non-ascii letters")
        else:
            generator = _make_enhanced_response_generator(compiler=cppcompiler, force_recompile=force_recompile)
            if generator is None:
                print("C++ enhancement is not available", file=sys.stderr)
                generator = generate_responses_python_only
    if generator is None:  # default option
        generator = generate_responses_python_only

    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=OFF")  # disable rollback to save time
        with _timereport("creating precomputed response table"):
            c.execute("DROP TABLE IF EXISTS responses")
            c.execute("CREATE TABLE responses (input_word TEXT, answer_word TEXT, response INT)")

        with _timereport("updating precomputed result"):
            q = "INSERT INTO responses VALUES (?,?,?)"
            params = generator(words)
            c.executemany(q, params)

        with _timereport("indexing the table"):
            c.execute("CREATE INDEX responses_idx ON responses (input_word, response)")
            c.execute("CREATE INDEX responses_idx2 ON responses (answer_word)")

        conn.commit()


def init_candidates(dbfile: str, tablename: str="candidates"):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS "{}"'.format(tablename))
        c.execute('CREATE TABLE "{}" AS SELECT word FROM words'.format(tablename))
        conn.commit()

def remove_table(dbfile: str, tablename: str):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS "{}"'.format(tablename))
        conn.commit()

def table_exists(dbfile: str, tablename: str):
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('SELECT 1 FROM sqlite_master WHERE name LIKE ?', (tablename,))
        res = c.fetchall()
    if len(res) > 1:
        print("There are %d tables named '%s'" % (len(res), tablename), file=sys.stderr)
    return (len(res) > 0)

def unused_candidate_name(dbfile: str)-> str:
    tables = list_candidate_tables(dbfile)
    i = 0
    while True:
        newtable = "candidates_{}".format(i)
        if newtable not in tables:
            return newtable
        i += 1

def list_candidate_tables(dbfile: str)-> list:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE name LIKE 'candidates_%'")
        tables = [row[0].lower() for row in c]
    return tables
    

def evaluate_candidates(dbfile: str, tablename: str="candidates"):
    with sqlite3.connect(dbfile) as conn:
        conn.create_function("log2", 1, math.log2)
        c = conn.cursor()

        c.execute('SELECT count(*) FROM "{}"'.format(tablename))
        n_candidates = c.fetchone()[0]
        c.execute("SELECT count(*) FROM words")
        n_words = c.fetchone()[0]
        answerfilter = "" if n_words == n_candidates else 'WHERE answer_word IN (SELECT word FROM "{}")'.format(tablename)
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
        LEFT JOIN (SELECT word, 1 AS is_candidate FROM "{candidatetable}") AS c
          ON t.input_word = c.word
        """.format(answerfilter=answerfilter, candidatetable=tablename)
        c.execute(q)   

        names = [c[0] for c in c.description]
        out = [{name: value for name, value in zip(names, row)} for row in c]
    return out

def update_candidate(dbfile: str, input_word: str, response: str, tablename: str="candidates"):    
    encoded = encode_response(int(response))
    with sqlite3.connect(dbfile) as conn:
        q = """
        DELETE FROM "{}" WHERE word NOT IN (
          SELECT
            answer_word
          FROM
            responses
          WHERE
            input_word = ? AND response = ?
        )
        """.format(tablename)
        param = (input_word, encoded)
        c = conn.cursor()        
        c.execute(q, param)
        conn.commit()

def get_candidates(dbfile: str, n: int=30, tablename: str="candidates")-> tuple:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('SELECT count(*) FROM "{}"'.format(tablename))
        count = c.fetchone()[0]
        if n is None:
            c.execute('SELECT word FROM "{}"'.format(tablename))
        else:
            assert type(n) == int and n > 0
            c.execute('SELECT word FROM "{}" LIMIT {}'.format(tablename, n))
        candidates = [row[0] for row in c.fetchall()]
    return count, candidates

def get_words(dbfile: str)-> list:
    with sqlite3.connect(dbfile) as conn:
        c = conn.cursor()
        c.execute('SELECT word FROM words')
        words = [row[0] for row in c.fetchall()]
    return words



def read_vocabfile(filepath: str):
    assert os.path.isfile(filepath), "'{}' does not exist".format(filepath)
    with open(filepath) as f:
        words = [line.strip() for line in f]
        # remove empty strings, just in case
        words = [w for w in words if len(w) > 0]
    return words

class WordleAISQLite:
    def __init__(self, dbfile: str, words: list or str=None, recompute: bool=False,
                 usecpp: bool=True, cppcompiler: str=None, force_recompile_cpp: bool=False,
                 ai_level: float=6, candidate_weight: float=0.3, decision_metric: str="mean_entropy"):
        self.dbfile = dbfile
        # parameters used for making a choice
        self.level = ai_level
        power = 5 - ai_level  # 0 -> 5, 1 -> 3, ..., 10 -> 5
        power = min(max(power, -5), 5)  # clip to [-5, 5]
        noise = math.pow(10, power)  # the smaller the stronger, 1e-5 ~ 1e+5
        self.decision_noise = noise
        self.candidate_weight = candidate_weight
        self.decision_metric = decision_metric
        
        if not os.path.isfile(dbfile) or recompute or (words is not None):
            if words is None:
                # no vocab info is given --> use default file
                vocabfile =  _package_data_file("wordle-vocab.txt")
                print("No vocab info is given, default vocabfile ('%s') is used" % vocabfile, file=sys.stderr)
                words = read_vocabfile(vocabfile)
            elif type(words) == str:
                # file path is given
                words = read_vocabfile(words)
            # otherwise words must be a list
            words = list(set(words)) # words must be unique
            with _timereport("database setup, this would take a while"):
                create_database(dbfile, words)
                compute_all_responses(dbfile, usecpp=usecpp, cppcompiler=cppcompiler, force_recompile=force_recompile_cpp)

    def __del__(self):
        if hasattr(self, "candidatetable"):
            remove_table(self.dbfile, self.candidatetable)

    def initialize(self):
        candidatetable = unused_candidate_name(self.dbfile)
        print("Candidate table for this session: '%s'" % candidatetable, file=sys.stderr)
        self.candidatetable = candidatetable
        init_candidates(self.dbfile, self.candidatetable)

    def evaluate(self, top_k: int=20, criterion: str="mean_entropy"):
        res = evaluate_candidates(self.dbfile, tablename=self.candidatetable)
        # sort by the given criterion
        # if that criterion is equal, then we prioritize candidate words
        res.sort(key=lambda row: (row[criterion], -row["is_candidate"]))
        # return only top_k
        return res[:top_k]

    def update(self, input_word: str, result: str or int):
        update_candidate(self.dbfile, input_word, result, tablename=self.candidatetable)

    def remaining_candidates(self, maxn: int=10)-> tuple:
        # return True if zero or one candidate left
        count, candidates = get_candidates(self.dbfile, n=maxn, tablename=self.candidatetable)
        return count, candidates
    
    def get_words(self)-> list:
        return get_words(self.dbfile)
    
    def pick_word(self):
        count, candidates = self.remaining_candidates()
        #print(count, candidates)
        if count == 1:
            return candidates[0]
        elif count == 0:
            print("Warning: No candidates left. This is a random choice")
            return random.choice(get_words())

        results = self.evaluate(top_k=10000, criterion=self.decision_metric)
        #print(results[:10], len(results))        
        words = [row["input_word"] for row in results]
        scores = [row[self.decision_metric] for row in results]  # score of eadch word, the smaller the better
        if self.decision_metric in ("mean_n", "max_n"):
            # we take log of the score to adjust for the scale
            # add 1p just in case to avoid the zero error
            scores = [math.log1p(s) for s in scores]
        
        # Flip the sign and adjust for the candidates
        for i, row in enumerate(results):
            scores[i] = row["is_candidate"] * self.candidate_weight - scores[i]
        # Subtract the maximum to normalize and avoid overflows
        maxscore = max(scores)
        scores = [s - maxscore for s in scores]
        # get choice weights with the given noise level
        weights = [math.exp(s / self.decision_noise) for s in scores]
        
        out = random.choices(words, weights=weights, k=1)
        return out[0]


def receive_user_command():
    while True:
        message = [
          "",
          "Type:",
          "  '[s]uggest <criterion>'     to let AI suggest a word (<criterion> is optional)",
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


def play(words: list):
    tmp = words[:5]
    if len(words) > 5:
        tmp.append("...")
    print("")
    print("Wordle game with %d words, e.g. %s" % (len(words), tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")

    # pick an answer randomly
    answer_word = random.choice(words)
    wordlen = len(answer_word)
        
    # define a set version of words for quick check for existence
    words_set = set(words)
    def _get_word():
        while True:
            x = input("> ").strip()
            if x in words_set or x == "give up":
                return x
            print("Invalid word: '%s'" % x)
                
    round = 0
    info = []
    while True:
        round += 1
        print("* Round %d *" % round)
        input_word = _get_word()
        if input_word == "give up":
            print("You lose. Answer: '%s'." % answer_word)
            return False
        res = wordle_response(input_word, answer_word)
        res = str(decode_response(res)).zfill(wordlen)
        info.append("  %s  %s" % (input_word, res))
        print("\n".join(info))
        if input_word == answer_word:
            print("Good job! You win! Answer: '%s'" % (round, answer_word))
            return True

def challenge(ai: WordleAISQLite):
    ai.initialize()
    count, words = ai.remaining_candidates(maxn=None)  # right after the initialization, all candidates are remaining
    assert count == len(words)
    tmp = words[:5]
    if len(words) > 5:
        tmp.append("...")
    print("")
    print("Wordle game against AI (level %s)" % ai.level)
    print("%d words, e.g. %s" % (len(words), tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")
    print("")

    # pick an answer randomly
    answer_word = random.choice(words)
    wordlen = len(answer_word)

    # define a set version of words for quick check for existence
    words_set = set(words)
    def _get_word():
        while True:
            x = input("Your turn > ").strip()
            if x in words_set or x == "give up":
                return x
            print("Invalid word: '%s'" % x)

    round = 0
    #header = "%-{ncol}s | %-{ncol}s".format(ncol=wordlen*2 + 2) % ("User", "AI")
    info = []
    info_mask = []
    user_done = False
    ai_done = False
    while True:
        round += 1
        print("* Round %d *" % round)
        # ai decision
        if not ai_done:
            with _timereport("AI thinking time"):
                ai_word = ai.pick_word()
            ai_res = wordle_response(ai_word, answer_word)
            ai_res = str(decode_response(ai_res)).zfill(wordlen)
            ai.update(ai_word, ai_res)
        else:
            ai_word = " " * wordlen
            ai_res = " " * wordlen
        
        # user decision
        if not user_done:
            user_word = _get_word()
            if user_word == "give up":
                print("You lose.")
                break
            user_res = wordle_response(user_word, answer_word)
            user_res = str(decode_response(user_res)).zfill(wordlen)
        else:
            user_word = " " * wordlen
            user_res = " " * wordlen

        info.append("  %s  %s | %s  %s" % (user_word, user_res, ai_word, ai_res))
        info_mask.append("  %s  %s | %s  %s" % (user_word, user_res, ai_word if ai_done else "*"*len(ai_word), ai_res))
        #print("\n".join(info))
        print("\n".join(info_mask))
        if user_word == answer_word and ai_word == answer_word:
            print("Good job! It's draw.")
            break
        elif user_word == answer_word:
            if ai_done:
                print("Well done!")
            else:
                print("Great job! You win!")
            user_done = True
        elif ai_word == answer_word:
            if user_done:
                print("Thanks for waiting.")
            else:
                print("You lose...")
            ai_done = True            
        
        if user_done and ai_done:
            break
    print("============================")
    print("Answer: '%s'" % answer_word)
    print("\n".join(info))
    print("============================")


def interactive(ai: WordleAISQLite, num_suggest: int=10, default_criterion: str="mean_entropy"):
    print("")
    print("Hello! This is Wordle AI with SQLite backend.")
    print("")

    ai.initialize()

    while True:
        maxn = 10  # max number of candidates to show
        count, candidates = ai.remaining_candidates(maxn=maxn)
        if count > maxn:
            candidates.append("...")
        if count > 1:
            print("%d remaining candidates: %s" % (count, candidates))
        elif count==1:
            print("'%s' should be the answer!" % candidates[0])
            break
        else:
            print("There is no candidate words consistent with the information...")
            break

        ans = receive_user_command()
        if ans[0] == "s":
            criterion = default_criterion if len(ans) < 2 else ans[1]
            with _timereport("candidate evaluation"):
                res = ai.evaluate(top_k=num_suggest, criterion=criterion)
            print("* Top %d candidates ordered by %s" % (len(res), criterion))
            print_eval_result(res)
        elif ans[0] == "u":
            ai.update(ans[1], ans[2])
        elif ans[0] == "e":
            break


def main():
    parser = ArgumentParser(description="Wordle AI with SQLite backend", formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("--dbfile", type=str, default="wordleai.db", help="SQLite database file")
    parser.add_argument("--vocabfile", type=str, help="Text file containing words")
    parser.add_argument("--default_criterion", type=str, default="mean_entropy",
                        choices=("max_n", "mean_n", "mean_entropy"), help="Criterion to suggest word")
    parser.add_argument("--num_suggest", type=int, default=20, help="Number of word suggestions")
    parser.add_argument("--recompute", action="store_true", help="Force recomputation of the database setup")
    parser.add_argument("--nocpp", action="store_true", help="Do not use C++ enhancement for precomputation")
    parser.add_argument("--force_recompile_cpp", action="store_true", help="Force recompiling the C++ script")
    parser.add_argument("--cppcompiler", type=str, help="C++ compiler command (if not given, the program search 'g++' or 'clang++')")
    parser.add_argument("--clean_candidate_tables", action="store_true", help="Remove existing candidate tables before the session")
    parser.add_argument("--play", action="store_true", help="Play your own game")
    parser.add_argument("--challenge", action="store_true", help="Challenge AI")
    parser.add_argument("--ai_level", type=float, default=6, help="Strength of AI in [0, 10]")
    parser.add_argument("--decision_metric", type=str, default="mean_entropy",
                        choices=("max_n", "mean_n", "mean_entropy"), help="Criterion to pick a word in challege mode")
    parser.add_argument("--candidate_weight", type=float, default=0.3)
    args = parser.parse_args()

    if args.clean_candidate_tables:
        if os.path.isfile(args.dbfile):
            for table in list_candidate_tables():
                remove_table(args.dbfile, table)

    if args.play:
        if args.vocabfile is not None:
            # use this vocab file
            words = read_vocabfile(args.vocabfile)
        elif args.dbfile is not None:
            words = get_words(args.dbfile)
        while True:
            play(words)
            while True:
                ans = input("One more game? (y/n) > ")
                ans = ans.strip().lower()[0:1]
                if ans in ("y", "n"):
                    break
            if ans == "n":
                print("")
                print("Thank you!")
                break
        return

    if args.challenge:
        #vocabfile = os.path.join(os.path.dirname(__file__), "vocabs/wordle.txt") if args.vocabfile is None else args.vocabfile
        ai = WordleAISQLite(args.dbfile, words=args.vocabfile, recompute=args.recompute,
                            usecpp=(not args.nocpp), cppcompiler=args.cppcompiler, force_recompile_cpp=args.force_recompile_cpp,
                            ai_level=args.ai_level, candidate_weight=args.candidate_weight, decision_metric=args.decision_metric)
        while True:
            challenge(ai)
            while True:
                ans = input("One more game? (y/n) > ")
                ans = ans.strip().lower()[0:1]
                if ans in ("y", "n"):
                    break
            if ans == "n":
                print("")
                print("Thank you!")
                break
        return

    # interactive session
    ai = WordleAISQLite(args.dbfile, words=args.vocabfile, recompute=args.recompute,
                        usecpp=(not args.nocpp), cppcompiler=args.cppcompiler, force_recompile_cpp=args.force_recompile_cpp)
    interactive(ai, num_suggest=args.num_suggest, default_criterion=args.default_criterion)
    print("")
    print("Thank you!")
    

if __name__ == "__main__":
    main()
