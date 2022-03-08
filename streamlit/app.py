#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
from logging import getLogger, basicConfig

import pandas as pd
import streamlit as st
from wordleaisql import __version__ as wordleaisql_version
from wordleaisql.approx import WordleAIApprox
from wordleaisql.utils import default_wordle_vocab

# Log message will be printed on the consle
logger = getLogger(__file__)
basicConfig(level=10, format="[%(levelname).1s|%(name)s|%(asctime).19s] %(message)s")


# constants
APP_VERSION = "0.0.1"
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

def show_wordle_judges(judges: list):
    rows = []
    _match_to_class = {"2": "exact", "1": "partial", "0": "nomatch"}
    for word, judge in judges:
        judge = str(judge).zfill(len(word))
        cells = ["""<td class="letter {}">{}</td>""".format(_match_to_class[match], letter) for letter, match in zip(word, judge)]
        rows.append("<tr>{}</tr>".format(" ".join(cells)))
    html = "<table>{}</table>".format(" ".join(rows))
    #print(html)
    return st.markdown(html, unsafe_allow_html=True)


# Want to cache this somehow, but gets error due to 'sqlite3.Connection object is unhashable'
#   both with st.cache and st.experimental_singleton
# Since making an AI object is trivial for typical vocabs with 10k words,
#   I let the AI is generated again at every rerun.
# @st.cache(allow_output_mutation=True)  # <-- this works but shows 'Running make_ai(...)' for a sec
def make_ai(words, word_pair_limit, candidate_samplesize):
    logger.info("Generating AI")
    ai = WordleAIApprox(vocabname="wordle", words=words, inmemory=True,
                        word_pair_limit=word_pair_limit, candidate_samplesize=candidate_samplesize)
    return ai

def main():
    st.markdown("""<style> {} </style>""".format(CSS), unsafe_allow_html=True)

    with st.sidebar:
        select_mode = st.selectbox("", ("Solver", "Challenge"), index=0)
        #select_word_pair_limit = st.selectbox("Word pair limit", (50000, 100000, 500000, 1000000), index=2)
        #select_candidate_sample = st.selectbox("Candidate sample size", (250, 500, 1000, 2000), index=1)
        st.markdown("App ver {appver} / [wordleaisql ver {libver}](https://github.com/kota7/wordleai-sql)".format(libver=wordleaisql_version, appver=APP_VERSION))

    
    if select_mode == "Solver":
        ai = make_ai(default_wordle_vocab(), word_pair_limit=WORD_PAIR_LIMIT, candidate_samplesize=CANDIDATE_SAMPLE_SIZE)
        words_set = set(ai.words)
        for w in words_set:
            wordlen = len(w)
            break

        if "solverJudges" not in st.session_state:
            st.session_state["solverJudges"] = []
        def _show_info():
            show_wordle_judges(st.session_state["solverJudges"])

        st.markdown("""
        ## WORDLE AI
        *with SQL backend*
        """)        
        word_sample = []
        for i, w in enumerate(words_set):
            word_sample.append(w)
            if i >= 6:
                break
        word_sample = ", ".join(word_sample)
        if len(words_set) > len(word_sample):
            word_sample += ", ..."
        st.write("Wordle game with %d words: [ %s ]" % (len(words_set), word_sample))

        _show_info()
        if len(st.session_state["solverJudges"]) > 0:
            cols = st.columns(5)
            if cols[0].button("Clear info"):
                st.session_state["solverJudges"].clear()
                st.experimental_rerun()
            if cols[1].button("Delete one line"):
                st.session_state["solverJudges"].pop()
                st.experimental_rerun()
        
        cols = st.columns(3)
        input_word = cols[0].text_input("Word", max_chars=wordlen, placeholder="weary")
        input_judge = cols[1].text_input("Judge", max_chars=wordlen, placeholder="02110")

        # workaround to locate the ENTER button to the bottom
        for _ in range(3):
            cols[2].write(" ")
        enter_button = cols[2].button("Enter")

        if enter_button:
            def _validate_input():
                if input_word == "":
                    return False
                if not input_word in words_set:
                    st.error("'%s' is not in the vocab" % input_word)
                    return False
                if not all(l in "012" for l in input_judge):
                    return False
                if len(input_judge) > wordlen:
                    return False
                return True

            if _validate_input():
                st.session_state["solverJudges"].append((input_word, input_judge.zfill(wordlen)))
                st.experimental_rerun()

        eval_button = st.button("Ask AI")
        def _eval():
            ai.clear_info()
            for w, r in st.session_state["solverJudges"]:
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
            st.write("%d answer word candidates remaining: [ %s ]" % (n_candidates, candidate_sample))

            res = ai.evaluate(top_k=15)
            if len(res) > 0:
                df = pd.DataFrame.from_records(res, columns=res[0]._fields)
                df = df.rename(columns={"max_n":"Max(n)", "mean_n":"Avg(n)", "mean_entropy": "Expected entropy", "is_candidate": "Can be answer"})
                df = df.set_index("input_word")
                st.markdown("*AI suggests the following words to try next*:")
                st.table(df)
            else:
                st.write("No word to evaluate")
        if eval_button:
            _eval()

    elif select_mode == "Challenge":
        st.warning("Challenge mode is under construction")

    


if __name__ == "__main__":
    main()