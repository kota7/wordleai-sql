#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
from logging import getLogger, basicConfig

import pandas as pd
import streamlit as st
from wordleaisql import __version__ as wordleaisql_version
from wordleaisql.approx import WordleAIApprox
from wordleaisql.utils import default_wordle_vocab, wordle_judge, decode_judgement

# Log message will be printed on the console
logger = getLogger(__file__)


# constants
APP_VERSION = "0.0.3"
WORD_PAIR_LIMIT = 500000
CANDIDATE_SAMPLE_SIZE = 500
CSS = """
td.letter {
    width: 60px;
    height: 30px;
    text-align: center;
    border: 5px white solid;
    border-bottom: 10px white solid;

    font-weight: 700;
    font-size: 30px;
    color: #eaeaea;
}
td.exact {
    background-color: green;
}
td.partial {
    background-color: orange;
}
td.nomatch {
    background-color: #666666;
}
"""

def wordle_judge_html(judges: list):
    rows = []
    _match_to_class = {"2": "exact", "1": "partial", "0": "nomatch"}
    for word, judge in judges:
        judge = str(judge).zfill(len(word))
        cells = ["""<td class="letter {}">{}</td>""".format(_match_to_class[match], "&nbsp;" if letter==" " else letter) for letter, match in zip(word, judge)]
        rows.append("<tr>{}</tr>".format(" ".join(cells)))
    html = "<table>{}</table>".format(" ".join(rows))
    #print(html)
    return html

def _thousand_sep(x: int, sep: str=",")-> str:
    return "{:,}".format(x).replace(",", sep)

def _init_state_if_not_exist(key: str, value):
    if key not in st.session_state:
        st.session_state[key] = value

# Want to cache this somehow, but gets error due to 'sqlite3.Connection object is unhashable'
#   both with st.cache and st.experimental_singleton
# Since making an AI object is trivial for typical vocabs with 10k words,
#   I let the AI is generated again at every rerun.
# @st.cache(allow_output_mutation=True)  # <-- this works but shows 'Running make_ai(...)' for a sec
def make_ai(words: list, word_pair_limit: int=500000, candidate_samplesize: int=500, strength: float=6):
    logger.info("Generating AI")
    ai = WordleAIApprox(vocabname="wordle", words=words, inmemory=True, strength=strength,
                        word_pair_limit=word_pair_limit, candidate_samplesize=candidate_samplesize)
    return ai

def main():
    st.markdown("""<style> {} </style>""".format(CSS), unsafe_allow_html=True)

    with st.sidebar:
        select_mode = st.selectbox("", ("Solver", "Challenge"), index=0)
        #select_word_pair_limit = st.selectbox("Word pair limit", (50000, 100000, 500000, 1000000), index=2)
        #select_candidate_sample = st.selectbox("Candidate sample size", (250, 500, 1000, 2000), index=1)
        if select_mode == "Challenge":
            ai_strength = st.selectbox("AI level", tuple(range(11)), index=6)
            visible = st.checkbox("Oppornent words are visible")
            alternate = st.checkbox("Choose a word in turns")
            ai_first = st.checkbox("AI plays first")

        st.markdown("App ver {appver} / [wordleaisql ver {libver}](https://github.com/kota7/wordleai-sql)".format(libver=wordleaisql_version, appver=APP_VERSION))
        

    
    if select_mode == "Solver":
        ai = make_ai(default_wordle_vocab(), word_pair_limit=WORD_PAIR_LIMIT, candidate_samplesize=CANDIDATE_SAMPLE_SIZE)
        words_set = set(ai.words)
        for w in words_set:
            wordlen = len(w)
            break

        _init_state_if_not_exist("solverHistory", [])

        def _solver_history():
            return st.session_state["solverHistory"]

        def _show_info(column=None):
            (st if column is None else column).markdown(wordle_judge_html(_solver_history()), unsafe_allow_html=True)

        st.markdown("""
        <font size="+6"><b>Wordle Solver</b></font> &nbsp; <i>with SQL backend</i>
        """, unsafe_allow_html=True)        
        word_sample = []
        for i, w in enumerate(words_set):
            word_sample.append(w)
            if i >= 6:
                break
        word_sample = ", ".join(word_sample)
        if len(words_set) > len(word_sample):
            word_sample += ", ..."
        st.write("%s words: [ %s ]" % (_thousand_sep(len(words_set)), word_sample))

        _show_info()
        if len(_solver_history()) > 0:
            cols = st.columns(5)  # make larger column to limit the space between buttons
            if cols[0].button("Clear info"):
                _solver_history().clear()
                st.experimental_rerun()
            if cols[1].button("Delete one line"):
                _solver_history().pop()
                st.experimental_rerun()
        
        cols = st.columns(3)
        input_word_solver = cols[0].text_input("Word", max_chars=wordlen, placeholder="weary")
        input_judge = cols[1].text_input("Judge", max_chars=wordlen, placeholder="02110",
                                         help=("Express the judge on the word by a sequence of {0,1,2}, where "
                                               "'2' is the match with correct place, "
                                               "'1' is the math with incorrect place, "
                                               "and '0' is no match."))
        # workaround to locate the ENTER button to the bottom
        for _ in range(3):
            cols[2].write(" ")

        enter_button = cols[2].button("Enter")
        if enter_button:
            def _validate_input():
                if input_word_solver == "":
                    return False
                if not input_word_solver in words_set:
                    st.info("'%s' is not in the vocab" % input_word_solver)
                    return False
                if not all(l in "012" for l in input_judge):
                    st.error("Judge must be a sequence of {0,1,2}, but '%s'" % input_judge)
                    return False
                if len(input_judge) != len(input_word_solver):
                    st.error("Judge must have the same length as the word, but '%s'" % input_judge)
                    return False
                return True

            if _validate_input():
                _solver_history().append((input_word_solver, input_judge.zfill(wordlen)))
                st.experimental_rerun()

        eval_button = st.button("Ask AI")
        def _eval():
            ai.clear_info()
            for w, r in _solver_history():
                ai.update(w, r)
            
            # report remaining candidates
            candidates = ai.candidates
            n_candidates = len(candidates)
            if n_candidates == 0:
                st.write("No answer word consistent with this information")
                return
            if n_candidates == 1:
                st.markdown("**{}** should be the answer!".format(candidates[0]))
                return
            candidate_sample = ", ".join(candidates[:6])
            if n_candidates > 6:
                candidate_sample += ", ..."
            st.write("%s answer candidates remaining: [ %s ]" % (_thousand_sep(n_candidates), candidate_sample))
            with st.spinner("AI is thinking..."):
                res = ai.evaluate(top_k=15)
            if len(res) > 0:
                df = pd.DataFrame.from_records(res, columns=res[0]._fields)
                df["is_candidate"] = ["yes" if c==1 else "no" for c in df["is_candidate"]]
                df = df.rename(columns={"max_n":"Max(n)", "mean_n":"Mean(n)", "mean_entropy": "Mean entropy", "is_candidate": "Candidate?"})                
                df = df.set_index("input_word")
                st.markdown("*AI suggests the following words to try next*:")
                st.table(df)
            else:
                st.write("No word to evaluate")
        if eval_button:
            _eval()

    elif select_mode == "Challenge":
        ai = make_ai(default_wordle_vocab(), word_pair_limit=WORD_PAIR_LIMIT, candidate_samplesize=CANDIDATE_SAMPLE_SIZE, strength=ai_strength)
        words_set = set(ai.words)
        for w in words_set:
            wordlen = len(w)
            break

        _init_state_if_not_exist("history", [])
        _init_state_if_not_exist("historyBuffer", [])  # infomation not seen by the oppornent
        _init_state_if_not_exist("answerWord", None)
        _init_state_if_not_exist("userDoneAt", -1)
        _init_state_if_not_exist("aiDoneAt", -1)
        _init_state_if_not_exist("aiNext", None)
        _init_state_if_not_exist("step", 0)

        def _show_history(visible_: bool):
            user_col, ai_col = st.columns(2)
            user_history = [(word, res) for word, res, userflg in st.session_state["history"] if userflg]
            #user_col.markdown("*User*")
            user_col.markdown(wordle_judge_html(user_history), unsafe_allow_html=True)
            ai_history = [(word if visible_ else " " * wordlen, res) for word, res, userflg in st.session_state["history"] if not userflg]
            #ai_col.markdown("*AI*")
            ai_col.markdown(wordle_judge_html(ai_history), unsafe_allow_html=True)

        def _ai_info():
            if visible:
                return [row[:2] for row in st.session_state["history"]]
            else:
                return [row[:2] for row in st.session_state["history"] if not row[2]]  # ai info only

        def _ai_decision():
            ai.clear_info()
            # let ai consume all information available
            for w, r in _ai_info():
                logger.info("AI's info: ('%s', '%s')", w, r)
                ai.update(w, r)
            return ai.pick_word()
        
        def _merge_buffer():
            st.session_state["history"] += st.session_state["historyBuffer"]
            st.session_state["historyBuffer"].clear()

        def _round_start():  # indicate that currently at the beginning of a round
            return (st.session_state["step"] % 2 == 0)

        def _winner():
            # if simultaneous move mode, winner cannot be determined in the middle of a round
            if (not alternate) and (not _round_start()):
                return "unfinished"
            if st.session_state["userDoneAt"] < 0 and st.session_state["aiDoneAt"] < 0:
                return "unfinished"  # neither player finished
            elif st.session_state["userDoneAt"] < 0:
                return "ai"  # only ai is done
            elif st.session_state["aiDoneAt"] < 0:
                return "user"  # only user is done

            # both player is done, need to compre the round to take
            if alternate:
                # farster player wins
                if st.session_state["userDoneAt"] > st.session_state["aiDoneAt"]:
                    return "ai"
                elif st.session_state["userDoneAt"] < st.session_state["aiDoneAt"]:
                    return "user"
                else:
                    logger.error("Draw should not occur in alternate mode, but (user done at %s, ai done at %s)",
                                 st.session_state["userDoneAt"], st.session_state["aiDoneAt"])
                    return "draw"  # but this should not occur theoretically
            else:
                # we compare by the residual of 2
                # i.e 0 and 1 are draw
                _user_done_round = int(st.session_state["userDoneAt"] / 2)
                _ai_done_round = int(st.session_state["aiDoneAt"] / 2)
                if _user_done_round > _ai_done_round:
                    return "ai"
                elif _user_done_round < _ai_done_round:
                    return "user"
                else:
                    return "draw"
        
        def _gameover():
            return (_winner() != "unfinished")

        st.markdown("""
        <font size="+6"><b>Challenge Wordle AI</b></font> &nbsp; <i>with SQL backend</i>
        """, unsafe_allow_html=True)        
        word_sample = []
        for i, w in enumerate(words_set):
            word_sample.append(w)
            if i >= 6:
                break
        word_sample = ", ".join(word_sample)
        if len(words_set) > len(word_sample):
            word_sample += ", ..."
        st.write("%s words: [ %s ]" % (_thousand_sep(len(words_set)), word_sample))

        if st.button("New Game"):
            st.session_state["history"].clear()
            st.session_state["historyBuffer"].clear()
            st.session_state["answerWord"] = random.choice(list(words_set))
            st.session_state["userDoneAt"] = -1
            st.session_state["aiDoneAt"] = -1
            st.session_state["aiNext"] = ai_first
            st.session_state["step"] = 0
            logger.info("Answer word = '%s'", st.session_state["answerWord"])

        # start loop
        logger.info("Session state: %s", st.session_state)
        # decision round
        if (not alternate) and _round_start():
            # at the begining of the round, we merge the buffer if any
            logger.info("Beginning of a round, we merge history buffer")
            _merge_buffer()

        if _gameover():
            winner = _winner()
            result = "You lose..." if winner == "ai" else "You win!" if winner == "user" else "Draw game."
            st.markdown("""
            *{}*
            Answer: '**{}**'
            """.format(result, st.session_state["answerWord"]))
            logger.info("Game is over. Winner = '%s'", _winner())
            _merge_buffer()  # merge action info if any before showing the final result
            _show_history(True)
            if winner == "user":
                if random.random() < 0.5:
                    st.balloons()
                else:
                    st.snow()
            st.stop()
        else:
            # start with showing the current info
            logger.info("Showing the history: %s", st.session_state["history"])
            logger.info("We have buffer: %s", st.session_state["historyBuffer"])
            _show_history(visible)
        
        cols = st.columns(2)
        input_word = cols[0].text_input("Word", max_chars=wordlen, placeholder="weary")
        # workaround to locate the ENTER button to the bottom
        for _ in range(3):
            cols[1].write(" ")
        enter_button = cols[1].button("Enter")

        # catch user's decision
        logger.info("Current step: %s", st.session_state["step"])
        if enter_button:
            logger.info("User input received '%s'", input_word)
            def _validate_input():
                if input_word == "":
                    return False
                if not input_word in words_set:
                    st.info("'%s' is not in the vocab" % input_word)
                    return False
                return True
            if _validate_input():
                logger.info("User input is valid '%s'", input_word)
                user_word = input_word
                user_res = wordle_judge(user_word, st.session_state["answerWord"])
                user_res = str(decode_judgement(user_res)).zfill(wordlen)
                if user_word == st.session_state["answerWord"]:
                    st.session_state["userDoneAt"] = st.session_state["step"]
                st.session_state["aiNext"] = True
                if alternate:
                    st.session_state["history"].append((user_word, user_res, True))
                else:
                    st.session_state["historyBuffer"].append((user_word, user_res, True))
                st.session_state["step"] += 1
                st.experimental_rerun()   # rerun to let the ai to make decision
              
        if st.session_state["aiNext"]:
            # ai's decision
            logger.info("AI is thinking...")
            with st.spinner("AI is thinking..."):
                ai_word = _ai_decision()
            ai_res = wordle_judge(ai_word, st.session_state["answerWord"])
            ai_res = str(decode_judgement(ai_res)).zfill(wordlen)
            if ai_word == st.session_state["answerWord"]:
                st.session_state["aiDoneAt"] = st.session_state["step"]
            st.session_state["aiNext"] = False
            if alternate:
                st.session_state["history"].append((ai_word, ai_res, False))
            else:
                st.session_state["historyBuffer"].append((ai_word, ai_res, False))
            st.session_state["step"] += 1
            st.experimental_rerun()  # rerun to update the info


    


if __name__ == "__main__":
    main()