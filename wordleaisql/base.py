# -*- coding: utf-8 -*-

import random
from typing import Type
from .utils import wordle_judge, encode_judgement, WordEvaluation, _dedup, _read_vocabfile

class WordleAI:
    """
    Base Wordle AI class.
    
    - Keeps words as the instance variable
    - Evaluation result is random
    - Pick a word in the candidate list randomly

    Args:
        vocabname (str):
            Name of vocaburary
        words (str or list or dict):
            If str, the path to a vocabulary file
            If list, the list of words
            If dict, mapping from word to the weight
    """
    def __init__(self, vocabname: str, words: str or list or dict=None, **kwargs):
        self.vocabname = vocabname
        self._vocabnames = [vocabname]  # no storage of other vocabs
        assert words is not None, "`words` must be supplied to setup the vocab '{}'".format(vocabname)
        if isinstance(words, dict):
            # maps a word to float
            self._words = words.copy()
        elif isinstance(words, list):
            # list of words with equal weight
            self._words = {w:1.0 for w in words}
        elif isinstance(words, str):
            # file path
            self._words = _read_vocabfile(words)
        else:
            raise TypeError("Unsupported type 'words': '{}'".format(type(words)))
        assert len(self._words) > 0, "Empty vocab is not allowed"
        wordlens = set(len(w) for w in self.words)
        assert len(wordlens) == 1, "word length must be equal, but '{}'".format(wordlens)

        self._info = []  # infomation of the judge result
        self._nonanswer_words = set([])  # words that cannot become an answer

    @property
    def name(self)-> str:
        return "Wordle AI (random)"

    @property
    def vocabnames(self)-> list:
        """Available vocab names"""
        return self._vocabnames if hasattr(self, "_vocabnames") else []

    @property
    def words(self)-> list:
        """All words that can be inputted"""
        return list(self._words.keys())

    @property
    def candidates(self)-> list:
        """Subset of answer words filtered by given information"""
        candidates = [w for w in self.words if w not in self.nonanswer_words]
        def _keep(candidate):
            for input_word, encoded_result in self.info:
                if wordle_judge(input_word, candidate) != int(encoded_result):
                    return False
            return True
        candidates = [c for c in candidates if _keep(c)]
        return candidates
        #return self._candidates

    @property
    def info(self)-> list:
        """List of (input_word, decoded_result)"""
        return self._info

    def clear_info(self):
        self.info.clear()

    @property
    def nonanswer_words(self)-> set:
        """Set of words that cannot become an answer"""
        return self._nonanswer_words

    def remove_from_answers(self, excluded_words: list):
        self._nonanswer_words |= set(excluded_words)

    # def set_candidates(self, candidates: list=None):
    #     """
    #     Set the candidate words.
    #     If candidates is none, then reset to the all answer words.
    #     """
    #     if candidates is not None:
    #         self._candidates = _dedup(candidates)
    #     else:
    #         self._candidates = self.words.copy()

    def evaluate(self, top_k: int=20, criterion: str="mean_entropy")-> list:
        """
        Evaluate input words and return the top ones in accordance with the given criterion
        """
        # this class picks a random candidate word
        n = min(top_k, len(self.candidates))
        results = {c: WordEvaluation(c, 1, 1, 1, 1) for c in random.sample(self.candidates, n)}
        if len(results) >= top_k:
            return list(results.values())
        # if there are less than top_k words in candidates add some answer words
        for w in self.words:
            if w in results:
                continue
            results[w] = WordEvaluation(w, 1, 1, 1, 0)
            if len(results) >= top_k:
                break
        results = list(results.values())
        results.sort(key=lambda row: -row[-1])
        return results

    def update(self, input_word: str, judge_result: int or str):
        """
        Update information on a judge result.

        Judge result is decoded, i.e. human-interpretable one such as '22001'
        """
        # self.set_candidates([c for c in self.candidates
        #                      if wordle_judge(input_word, c) == encode_judgement(int(judge_result))])
        self.info.append((input_word, encode_judgement(int(judge_result))))

    def pick_word(self, criterion: str="mean_entropy")-> str:
        """Pick an input word"""
        if len(self.candidates) > 0:
            return random.choice(self.candidates)
        print("Warning: There is no answer candidates remaining")
        return random.choice(self.words)
    
    def choose_answer_word(self, weighted: bool=True):
        """Randomly choose an answer word in accordance with the given weight"""
        if not weighted:
            return random.choice(self.words)

        vals = []
        weights = []
        for w, p in self._words.items():
            if p > 0:
                vals.append(w)
                weights.append(p)
        assert len(vals) > 0, "There is no word with positive weight"
        return random.choices(vals, weights, k=1)[0]