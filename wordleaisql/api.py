# -*- coding: utf-8 -*-

import random
import re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from logging import basicConfig, getLogger
logger = getLogger(__name__)

from .base import WordleAI
from .utils import show_word_evaluations, default_wordle_vocab, _timereport, wordle_judge, decode_judgement, _read_vocabfile
from .sqlite import WordleAISQLite
from .approx import WordleAIApprox
from . import __version__

def interactive(ai: WordleAI, num_suggest: int=10, default_criterion: str="mean_entropy"):
    print("")
    print("Hi, this is %s." % ai.name)
    print("")
    ai.set_candidates()  # initialize all candidates

    def _receive_input():
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
            ans = re.sub(r"\s+", " ", ans.strip())
            ans = ans.split(" ")
            if len(ans) <= 0: continue
            if len(ans[0]) <= 0: continue

            if ans[0][0] == "s":
                if len(ans) > 1:
                    criterion = ans[1]
                    if criterion not in ("max_n", "mean_n", "mean_entropy"):
                        print("Invalid <criterion> ('%s' is given)" % criterion)
                        continue
                    return ["s", criterion]
                else:
                    return ["s"]
            elif ans[0][0] == "u":
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
            elif ans[0][0] == "e":
                return ["e"]
            
    while True:
        maxn = 10  # max number of candidates to show
        n_remain = len(ai.candidates)
        remain = ai.candidates[:maxn]
        if n_remain > maxn:
            remain.append("...")
        if n_remain > 1:
            print("%d remaining candidates: %s" % (n_remain, remain))
        elif n_remain==1:
            print("'%s' should be the answer!" % remain[0])
            break
        else:
            print("There is no candidate words consistent with the information...")
            break

        ans = _receive_input()
        if ans[0] == "s":
            criterion = default_criterion if len(ans) < 2 else ans[1]
            with _timereport("AI evaluation"):
                res = ai.evaluate(top_k=num_suggest, criterion=criterion)
            print("* Top %d candidates ordered by %s" % (len(res), criterion))
            show_word_evaluations(res)
        elif ans[0] == "u":
            ai.update(ans[1], ans[2])
        elif ans[0] == "e":
            break
    print("Thank you!")


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
    input_words_set = set(words)
    def _get_word():
        while True:
            x = input("> ").strip()
            if x in input_words_set or x == "give up":
                return x
            print("Invalid word: '%s'" % x)
                
    round_ = 0
    info = []
    while True:
        round_ += 1
        print("* Round %d *" % round_)
        input_word = _get_word()
        if input_word == "give up":
            print("You lose. Answer: '%s'." % answer_word)
            return False
        res = wordle_judge(input_word, answer_word)
        res = str(decode_judgement(res)).zfill(wordlen)
        info.append("  %s  %s" % (input_word, res))
        print("\n".join(info))
        if input_word == answer_word:
            print("Good job! You win! Answer: '%s'" % answer_word)
            return True

def challenge(ai: WordleAI, max_round: int=20):
    ai.set_candidates()
    n_ans = len(ai.candidates)
    n_words = len(ai.words)

    tmp = ai.words[:5]
    if n_words > 5:
        tmp.append("...")
    print("")
    print("Wordle game against %s level %s" % (ai.name, ai.strength))
    print("%d words, e.g. %s" % (n_words, tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")
    print("")

    # pick an answer randomly
    answer_word = random.choice(ai.words)
    wordlen = len(answer_word)

    # define a set version of words for quick check for existence
    words_set = set(ai.words)
    def _get_word():
        while True:
            x = input("Your turn > ").strip()
            if x in words_set or x == "give up":
                return x
            print("Invalid word: '%s'" % x)

    round_ = 0
    #header = "%-{ncol}s | %-{ncol}s".format(ncol=wordlen*2 + 2) % ("User", "AI")
    info = []
    info_mask = []
    user_done = False
    ai_done = False
    while True:
        if round_ >= max_round:
            break
        round_ += 1
        print("* Round %d *" % round_)
        # ai decision
        if not ai_done:
            with _timereport("AI thinking"):
                ai_word = ai.pick_word()
            ai_res = wordle_judge(ai_word, answer_word)
            ai_res = str(decode_judgement(ai_res)).zfill(wordlen)
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
            user_res = wordle_judge(user_word, answer_word)
            user_res = str(decode_judgement(user_res)).zfill(wordlen)
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
    print("===============================")
    print("Answer: '%s'" % answer_word)
    print("\n".join(info))
    print("===============================")


def main():
    basicConfig(level=20, format="[%(levelname)s] %(message)s")
    parser = ArgumentParser(description="Wordle AI with SQL backend", formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("-b", "--backend", type=str, default="sqlite", choices=["sqlite", "approx", "bq", "random"], help="AI type")
    parser.add_argument("--vocabname", default="wordle", type=str, help="Name of vocabulary")
    parser.add_argument("--vocabfile", type=str, help="Text file containing words. If not supplied, default wordle vocab is used")
    parser.add_argument("--resetup", action="store_true", help="Setup the vocabulary if already exists")
    parser.add_argument("--sqlitefile", type=str, 
                        help=("SQLite database file. If not supplied, we first search env variable 'WORDLEAISQL_DBFILE'. "
                              "If the env variable is not defined, then ./wordleai.db is used"))
    parser.add_argument("--word_pair_limit", type=int, default=1000000,
                        help="Maximum number of (input word, answer word) pairs computed for approximate evaluation")
    parser.add_argument("--candidate_samplesize", type=int, default=1000,
                        help="Sample size of answer word for approximate evaluation")
    parser.add_argument("--bq_credential", type=str, help="Credential json file for a GCP service client")
    parser.add_argument("--bq_project", type=str, help="GCP project id (if not supplied, inferred from the credential default)")
    parser.add_argument("--bq_location", type=str, default="US", help="GCP location")
    parser.add_argument("--partition_size", type=int, default=200, help="Partition size of judges table")

    parser.add_argument("--suggest_criterion", type=str, default="mean_entropy", choices=["max_n", "mean_n", "mean_entropy"],
                        help="Criterion for an AI to sort the word suggestions")
    parser.add_argument("--num_suggest", type=int, default=20, help="Number of suggestion to print")
    parser.add_argument("--ai_strength", type=float, default=5, help="Strength of AI in [0, 10] in challenge mode")
    parser.add_argument("--decision_metric", type=str, default="mean_entropy", choices=["max_n", "mean_n", "mean_entropy"],
                        help="Criterion for an AI to use in challenge mode")
    parser.add_argument("--candidate_weight", type=float, default=0.3, help="Weight applied to the answer candidate words in challenge mode")

    parser.add_argument("--play", action="store_true", help="Play your own game without AI")
    parser.add_argument("--challenge", action="store_true", help="Challenge AI")
    parser.add_argument("--max_round", type=int, default=20, help="Maximum rounds in challenge mode")

    parser.add_argument("--no_cpp", action="store_true", help="Not to use C++ script even if available")
    parser.add_argument("--cpp_recompile", action="store_true", help="Compile the C++ script again even if the source script is not updated")
    parser.add_argument("--cpp_compiler", type=str, help="Command name of the C++ compiler")

    parser.add_argument("--version", action="store_true", help="Show the program version")

    args = parser.parse_args()
    if args.version:
        print("wordleaisql v%s" % __version__)
        return

    #print(args)
    words = default_wordle_vocab() if args.vocabfile is None else _read_vocabfile(args.vocabfile)
    #print(words)
    if args.play:
        while True:
            play(words)
            while True:
                ans = input("One more game? (y/n) > ")
                ans = ans.strip().lower()[0:1]
                if ans in ("y", "n"):
                    break
            if ans == "n":
                print("Thank you!")
                return

    if args.backend == "sqlite":
        ai = WordleAISQLite(args.vocabname, words, dbfile=args.sqlitefile, resetup=args.resetup,
                            decision_metric=args.decision_metric, candidate_weight=args.candidate_weight, strength=args.ai_strength,
                            use_cpp=(not args.no_cpp), cpp_recompile=args.cpp_recompile, cpp_compiler=args.cpp_compiler)
        logger.info("SQLite database: '%s', vocabname: '%s'", ai.dbfile, ai.vocabname)
    elif args.backend == "approx":
        ai = WordleAIApprox(args.vocabname, words, dbfile=args.sqlitefile, resetup=args.resetup,
                            word_pair_limit=args.word_pair_limit, candidate_samplesize=args.candidate_samplesize,
                            decision_metric=args.decision_metric, candidate_weight=args.candidate_weight, strength=args.ai_strength)
        logger.info("SQLite database: '%s', word pair limit: %d, answer word sample size: %d, vocabname: '%s'",
                    ai.dbfile, ai.word_pair_limit, ai.candidate_samplesize, ai.vocabname)
    elif args.backend == "bq":
        from .bigquery import WordleAIBigquery
        ai = WordleAIBigquery(args.vocabname, words, resetup=args.resetup,
                              credential_jsonfile=args.bq_credential, project=args.bq_project,
                              location=args.bq_location, partition_size=args.partition_size,
                              decision_metric=args.decision_metric, candidate_weight=args.candidate_weight, strength=args.ai_strength)
        logger.info("GCP project: '%s', location: '%s', vocabname: '%s'", ai.project, ai.location, ai.vocabname)
    elif args.backend == "random":
        ai = WordleAI(args.vocabname, words)
    else:
        raise ValueError("Backend not supported '%s'" % args.backend)

    if args.challenge:
        while True:
            challenge(ai, args.max_round)
            while True:
                ans = input("One more game? (y/n) > ")
                ans = ans.strip().lower()[0:1]
                if ans in ("y", "n"):
                    break
            if ans == "n":
                print("Thank you!")
                return
    else:
        return interactive(ai, num_suggest=args.num_suggest, default_criterion=args.suggest_criterion)