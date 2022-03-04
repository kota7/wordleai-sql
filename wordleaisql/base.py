# -*- coding: utf-8 -*-

import random
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
        words (str of list): 
            If str, the path to a vocabulary file
            If list, the list of words
    """
    def __init__(self, vocabname: str, words: list or str, **kwargs):
        self.vocabname = vocabname
        self._vocabnames = [vocabname]  # no storage of other vocabs
        self._words = _read_vocabfile(words) if type(words) == str else _dedup(words)
        wordlens = set(len(w) for w in self.words)
        assert len(wordlens) == 1, "word length must be equal, but '{}'".format(wordlens)

        self.set_candidates()
    
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
        return self._words

    @property
    def candidates(self)-> list:
        """Subset of answer words filtered by given information"""
        return self._candidates

    def set_candidates(self, candidates: list=None):
        """
        Set the candidate words.
        If candidates is none, then reset to the all answer words.
        """
        if candidates is not None:
            self._candidates = _dedup(candidates)
        else:
            self._candidates = self.words.copy()
    
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
        Update candidate words by the judge result.

        Judge result is decoded, i.e. human-interpretable one such as '22001'
        """
        self.set_candidates([c for c in self.candidates
                             if wordle_judge(input_word, c) == encode_judgement(int(judge_result))])
        
    def pick_word(self, criterion: str="mean_entropy")-> str:
        """Pick an input word"""
        if len(self.candidates) > 0:
            return random.choice(self.candidates)
        print("Warning: There is no answer candidates remaining")
        return random.choice(self.words)