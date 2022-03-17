# -*- coding: utf-8 -*-

import os
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
    #ai.set_candidates()  # initialize all candidates
    ai.clear_info()
    words_set = set(ai.words)

    def _receive_input(words_set: set):
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
                    print("'%s' is invalid result expression" % result)
                    continue
                if word not in words_set:
                    print("'%s' is not in the vocab" % word)
                    continue
                if len(word) < len(result):
                    print("Word and result length mismatch")
                    continue
                return ["u", word, result]
            elif ans[0][0] == "e":
                return ["e"]
            
    while True:
        maxn = 10  # max number of candidates to show
        cur_candidates = ai.candidates
        n_remain = len(cur_candidates)
        remain = cur_candidates[:maxn]
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

        ans = _receive_input(words_set)
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


def play(words: list or dict, vocabname: str="No name", answer_weight: bool=True):
    if isinstance(words, list):
        words = {w:1 for w in words}  # assign equal weight

    tmp = list(words)[:5]
    if len(words) > 5:
        tmp.append("...")
    print("")
    print("Enjoy wordle game (vocabname: '%s', containing %d words, e.g. %s)" % (vocabname, len(words), tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")

    # pick an answer randomly
    if answer_weight:
        vals = []
        weights = []
        for w, p in words.items():
            if p > 0:
                vals.append(w)
                weights.append(p)
        assert len(vals) > 0, "There is no word with positive weight"
        answer_word = random.choices(vals, weights, k=1)[0]
    else:
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

def challenge(ai: WordleAI, answer_weight: bool=True, max_round: int=20, visible: bool=False,
              alternate: bool=False, ai_first: bool=False, continue_after_result: bool=False):
    #ai.set_candidates()
    ai.clear_info()
    n_ans = len(ai.candidates)
    n_words = len(ai.words)

    tmp = ai.words[:5]
    if n_words > 5:
        tmp.append("...")
    print("")
    print("Wordle game against %s, AI strength: %s, vocabname: %s" % (ai.name, ai.strength, ai.vocabname))
    print("%d words, e.g. %s" % (n_words, tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")
    print("")

    # pick an answer randomly
    answer_word = ai.choose_answer_word(weighted=answer_weight)
    wordlen = len(answer_word)

    # define a set version of words for quick check for existence
    words_set = set(ai.words)
    def _get_word():
        while True:
            x = input("Your turn > ").strip()
            if x in words_set or x == "give up":
                return x
            print("Invalid word: '%s'" % x)

    user_history, ai_history = [], []
    user_done, ai_done = False, False  # flag of finding answer
    giveup = False  # flag user gave up
    ai_turn = ai_first
    winner = "unfinished"  # {unfinished, draw, user, ai}
    def _show_history():
        _user_history = user_history.copy()
        _ai_history = ai_history.copy()
        #print(_user_history)
        #print(_ai_history)
        # fix the legngth difference, if any
        if not visible:
            _ai_history = [(("*" if w in words_set else " ") * wordlen, r) for w, r in _ai_history]
        # pad empty rows
        while len(_ai_history) < len(_user_history):
            _ai_history.append((" " * wordlen, " " * wordlen))
        while len(_user_history) < len(_ai_history):
            _user_history.append((" " * wordlen, " " * wordlen))
        out = []
        for u, a in zip(_user_history, _ai_history):
            out.append("  %s  %s  |  %s  %s" % tuple(u + a))
        print("\n".join(out))

    for round_ in range(max_round):
        print("* Round %d *" % (round_ + 1))
        # clear prev round result
        tmp = " " * wordlen
        ai_word, ai_res, user_word, user_res = tmp, tmp, tmp, tmp
        for _ in range(2):  # loop over two users
            skipped = False  # flag no decision has been made by this user
            if ai_turn:
                if ai_done:
                    skipped = True
                else:
                    with _timereport("AI thinking"):
                        ai_word = ai.pick_word()
                    ai_res = wordle_judge(ai_word, answer_word)
                    ai_res = str(decode_judgement(ai_res)).zfill(wordlen)
                    ai.update(ai_word, ai_res)
                    ai_history.append((ai_word, ai_res))
                    if ai_word == answer_word:
                        ai_done = True
                ai_turn = False
            else:
                if (user_done or giveup):
                    skipped = True
                else:
                    user_word = _get_word()
                    if user_word == "give up":
                        giveup = True
                    else:
                        user_res = wordle_judge(user_word, answer_word)
                        user_res = str(decode_judgement(user_res)).zfill(wordlen)
                        user_history.append((user_word, user_res))
                        if user_word == answer_word:
                            user_done = True
                        if visible and alternate and (user_word in words_set):
                            # ai learns the user output
                            ai.update(user_word, user_res)
                ai_turn = True

            if alternate and (not skipped):
                _show_history() # show the history at the end of one move
                # check the winner
                if winner == "unfinished":
                    if ai_done:
                        winner = "ai"
                    elif user_done:
                        winner = "user"
                if winner != "unfinished":
                    if (not continue_after_result) or visible:
                        # visible --> answer is already seen
                        # not continue_after_result --> no reason to continue
                        break  # go to the round end

        if not alternate:
            _show_history()  # show the history at the end of each found
            if visible and (user_word in words_set): 
                # ai learns user's output at the end of round
                ai.update(user_word, user_res)
            # check the winner
            if winner == "unfinished":
                if ai_done and user_done:
                    winner = "draw"
                elif ai_done:
                    winner = "ai"
                elif user_done:
                    winner = "user"

        if continue_after_result and (not visible):
            if user_done and ai_done:
                break
        else:
            if winner != "unfinished":
                break
    print("===============================")
    if winner == "user":
        print("Great job! You win!")
    elif winner == "ai":
        print("You lose...")
    else:
        print("Good job. It's draw.")
    print("Answer: '%s'" % answer_word)
    visible = True
    _show_history()
    print("===============================")
            

def main():
    parser = ArgumentParser(description="Wordle AI with SQL backend", formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("-b", "--backend", type=str, default="approx", choices=["sqlite", "approx", "bq", "random"], help="AI type")
    parser.add_argument("--vocabname", default=None, type=str, help="Name of vocabulary")
    parser.add_argument("--vocabfile", type=str, help="Text file containing words. If not supplied, default wordle vocab is used")
    parser.add_argument("--resetup", action="store_true", help="Setup the vocabulary if already exists")
    parser.add_argument("--sqlitefile", type=str, 
                        help=("SQLite database file. If not supplied, we first search env variable 'WORDLEAISQL_DBFILE'. "
                              "If the env variable is not defined, then ./wordleai.db is used"))
    parser.add_argument("--inmemory", action="store_true", help="Use in-memory database. Only applicable with `-b approx`")
    parser.add_argument("--word_pair_limit", type=int, default=500000,
                        help="Maximum number of (input word, answer word) pairs computed for approximate evaluation")
    parser.add_argument("--candidate_samplesize", type=int, default=500,
                        help="Sample size of answer word for approximate evaluation")
    parser.add_argument("--bq_credential", type=str, help="Credential json file for a GCP service client")
    parser.add_argument("--bq_project", type=str, help="GCP project id (if not supplied, inferred from the credential default)")
    parser.add_argument("--bq_location", type=str, default="US", help="GCP location")
    parser.add_argument("--partition_size", type=int, default=200, help="Partition size of judges table")

    parser.add_argument("--suggest_criterion", type=str, default="mean_entropy", choices=["max_n", "mean_n", "mean_entropy"],
                        help="Criterion for an AI to sort the word suggestions")
    parser.add_argument("--num_suggest", type=int, default=20, help="Number of suggestion to print")

    parser.add_argument("--play", action="store_true", help="Play your own game without AI")
    parser.add_argument("--no_answer_weight", action="store_true", help="Not to use the answer weight in play and challenge mode")
    parser.add_argument("--challenge", action="store_true", help="Challenge AI")
    parser.add_argument("--max_round", type=int, default=20, help="Maximum rounds in challenge mode")
    parser.add_argument("--visible", action="store_true", help="Opponent words are visible in challenge mode")
    parser.add_argument("--alternate", action="store_true", help="Decisions are made in turn in challenge mode")
    parser.add_argument("--ai_first", action="store_true", help="AI makes the first decision in challenge mode")
    parser.add_argument("--continue_after_result", action="store_true", help="Continue the game after result is determined in challenge mode")
    parser.add_argument("--ai_strength", type=float, default=6, help="Strength of AI in [0, 10] in challenge mode")
    parser.add_argument("--decision_metric", type=str, default="mean_entropy", choices=["max_n", "mean_n", "mean_entropy"],
                        help="Criterion for an AI to use in challenge mode")
    parser.add_argument("--candidate_weight", type=float, default=0.3, help="Weight applied to the answer candidate words in challenge mode")

    parser.add_argument("--no_cpp", action="store_true", help="Not to use C++ script even if available")
    parser.add_argument("--cpp_recompile", action="store_true", help="Compile the C++ script again even if the source script is not updated")
    parser.add_argument("--cpp_compiler", type=str, help="Command name of the C++ compiler")

    parser.add_argument("--debug", action="store_true", help="Show debug messages")
    parser.add_argument("--version", action="store_true", help="Show the program version")

    args = parser.parse_args()
    #print(args)
    if args.version:
        print("wordleaisql v%s" % __version__)
        return
    basicConfig(level=10 if args.debug else 20, format="[%(levelname)s] %(message)s")

    #print(args)
    if args.vocabfile is None:
        words = default_wordle_vocab()
        vocabname = "wordle" if args.vocabname is None else args.vocabname
        #print(vocabname)
    else:
        words = _read_vocabfile(args.vocabfile)
        vocabname = args.vocabname
        if vocabname is None:
            vocabname = re.sub(r"\..*$", "", os.path.basename(args.vocabfile))

    #print(words)
    if args.play:
        while True:
            play(words, vocabname=vocabname, answer_weight=(not args.no_answer_weight))
            while True:
                ans = input("One more game? (y/n) > ")
                ans = ans.strip().lower()[0:1]
                if ans in ("y", "n"):
                    break
            if ans == "n":
                print("Thank you!")
                return

    if args.backend == "sqlite":
        if args.inmemory:
            logger.warning("`--inmemory` only applicable with `-b approx`")
        ai = WordleAISQLite(vocabname, words, dbfile=args.sqlitefile, resetup=args.resetup,
                            decision_metric=args.decision_metric, candidate_weight=args.candidate_weight, strength=args.ai_strength,
                            use_cpp=(not args.no_cpp), cpp_recompile=args.cpp_recompile, cpp_compiler=args.cpp_compiler)
        logger.info("SQLite database: '%s', vocabname: '%s'", ai.dbfile, ai.vocabname)
    elif args.backend == "approx":
        ai = WordleAIApprox(vocabname, words, dbfile=args.sqlitefile, inmemory=args.inmemory, resetup=args.resetup,
                            word_pair_limit=args.word_pair_limit, candidate_samplesize=args.candidate_samplesize,
                            decision_metric=args.decision_metric, candidate_weight=args.candidate_weight, strength=args.ai_strength)
        logger.info("SQLite database: '%s', word pair limit: %d, answer word sample size: %d, vocabname: '%s'",
                    ai.dbfile, ai.word_pair_limit, ai.candidate_samplesize, ai.vocabname)
    elif args.backend == "bq":
        from .bigquery import WordleAIBigquery
        ai = WordleAIBigquery(vocabname, words, resetup=args.resetup,
                              credential_jsonfile=args.bq_credential, project=args.bq_project,
                              location=args.bq_location, partition_size=args.partition_size,
                              decision_metric=args.decision_metric, candidate_weight=args.candidate_weight, strength=args.ai_strength)
        logger.info("GCP project: '%s', location: '%s', vocabname: '%s'", ai.project, ai.location, ai.vocabname)
    elif args.backend == "random":
        ai = WordleAI(vocabname, words)
    else:
        raise ValueError("Backend not supported '%s'" % args.backend)

    if args.challenge:
        while True:
            challenge(ai, answer_weight=(not args.no_answer_weight),
                      max_round=args.max_round, visible=args.visible, alternate=args.alternate,
                      ai_first=args.ai_first, continue_after_result=args.continue_after_result)
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