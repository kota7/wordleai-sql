# distutils: language=c++
# -*- coding: utf-8 -*-

from libcpp.vector cimport vector
from libcpp.map cimport map
from libcpp cimport bool

def wordle_response_cython(str input_word, str answer_word):
    #assert len(input_word) == len(answer_word), "Word length mismatch ([] vs {})".format(len(input_word), len(answer_word))
    cdef:
        int i, out, power
        bool m, n
        str a, b
    cdef vector[bool] exactmatch = [a==b for a, b in zip(input_word, answer_word)]
    cdef map[char, int] lettercount
    for b, m in zip(answer_word, exactmatch):
        if m: continue
        if b in lettercount:
            lettercount[b] = 1
        else:
            lettercount[b] += 1

    cdef vector[bool] partialmatch = [False] * len(input_word)
    for i, (a, m) in enumerate(zip(input_word, exactmatch)):
        if m: continue
        print(dir(lettercount))
        if a in lettercount and lettercount[a] > 0:
            lettercount[a] -= 1
            partialmatch[i] = True
    # Define the response as an integer of base 3
    #   with 2: exact, 1: partial, 0: none
    # To reduce the variable size, we store the integer of base 10
    out = 0
    power = 1
    for m, n in zip(reversed(exactmatch), reversed(partialmatch)):
        if m:
            out += power*2
        elif n:
            out += power
        power *= 3
    return out