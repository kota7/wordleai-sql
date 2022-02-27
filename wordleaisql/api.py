# -*- coding: utf-8 -*-

import random
import re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from .base import WordleAI
from .utils import show_word_evaluations, default_wordle_vocab, _timereport, wordle_judge, decode_judgement


def interactive(ai: WordleAI, num_suggest: int=10, default_criterion: str="mean_entropy"):
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
            if len(ans) <= 0:
                continue

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


def play(input_words: list, answer_words: list=None):
    tmp = input_words[:5]
    if len(words) > 5:
        tmp.append("...")
    print("")
    print("Wordle game with %d words, e.g. %s" % (len(input_words), tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")

    if answer_words is None:
        answer_words = input_words
    # pick an answer randomly
    answer_word = random.choice(answer_words)
    wordlen = len(answer_word)
        
    # define a set version of words for quick check for existence
    input_words_set = set(input_words)
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
        res = wordle_response(input_word, answer_word)
        res = str(decode_response(res)).zfill(wordlen)
        info.append("  %s  %s" % (input_word, res))
        print("\n".join(info))
        if input_word == answer_word:
            print("Good job! You win! Answer: '%s'" % answer_word)
            return True

def challenge(ai: WordleAI):
    ai.set_candidates()
    n_ans = len(ai.candidates)
    n_words = len(ai.input_words)

    tmp = ai.input_words[:5]
    if n_words > 5:
        tmp.append("...")
    print("")
    print("Wordle game against AI")
    print("%d words, e.g. %s" % (n_words, tmp))
    print("")
    print("Type your guess, or 'give up' to finish the game")
    print("")

    # pick an answer randomly
    answer_word = random.choice(ai.answer_words)
    wordlen = len(answer_word)

    # define a set version of words for quick check for existence
    words_set = set(ai.input_words)
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
    parser = ArgumentParser(description="Wordle AI", formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("-b", "--backend", default="random", type=str, help="AI backend")
    parser.add_argument("--vocabfile", type=str, help="Text file containing words")
    parser.add_argument("--play", action="store_true", help="Play your own game")
    parser.add_argument("--challenge", action="store_true", help="Challenge AI")
    args = parser.parse_args()
    
    if args.play:
        words = default_wordle_vocab()        
    elif args.challenge:
        words = default_wordle_vocab()
        challenge(WordleAI("wordle", words))
    else:
        words = default_wordle_vocab()
        interactive(WordleAI("wordle", words))
    
    