# -*- coding: utf-8 -*-


from .utils import wordle_judge, encode_judgement, WordEvaluation

class WordleAI:
    """
    Base Wordle AI class.
    
    - Keeps input and answer words as instance variables
    - Evaluation result is random
    - Pick a word in the candidate list randomly
    """
    def __init__(self, vocabname: str, input_words: list,
                 answer_words: list=None, resetup: bool=False, **kwargs):
        if resetup or (vocabname not in self.vocabnames):
            self.setup(vocabname, input_words, answer_words, **kwargs)

    def setup(self, vocabname: str, input_words: list, answer_words: list=None):
        self.vocabname = vocabname
        self._vocabnames = [vocabname]  # no storage of other vocabs
        self._input_words = list(dict.fromkeys(input_words))  # remove duplicates
        self._answer_words = answer_words or self._input_words.copy()
        self.set_candidates()

    @property
    def vocabnames(self)-> list:
        """Available vocab names"""
        return self._vocabnames if hasattr(self, "_vocabnames") else []
    
    @property
    def input_words(self)-> set:
        """All words that can be inputted"""
        return self._input_words

    @property
    def answer_words(self)-> list:
        """All words that can become answer"""
        return self._answer_words

    @property
    def candidates(self)-> list:
        """Subset of answer words filtered by given information"""
        return self._candidates

    def set_candidates(self, candidates: list=None):
        """
        Set the candidate words.
        If candidates is none, then reset to the all answer words.
        """
        self._candidates = candidates or self.answer_words
    
    def evaluate(self, top_k: int=20, criterion: str="mean_entropy", candidates: list=None)-> list:
        """
        Evaluate input words and return the top ones in accordance with the given criterion
        """
        # this class picks a random candidate word
        results = [WordEvaluation(c, 1, 1, 1, 1) for c in self.candidates[:top_k]]
        if len(results) >= top_k:
            return results
        # if there are less then top_k words in candidates add some answer words
        results += [WordEvaluation(w, 1, 1, 1, 0) for w in self.input_words[:(top_k-len(results))]]
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
        result = self.evaluate(criterion=criterion, top_k=1)
        return result[0].input_word