# -*- coding: utf-8 -*-

import sqlite3
from contextlib import contextmanager

from .base import WordleAI

class WordleSqliteAI(WordleAI):
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.dbfile)
        try:
            yield conn
        finally:
            conn.close()
    
    def _sql(self, query, read: bool, params=None, many: bool=False):
        with self._connect() as conn:
            c = conn.cursor()            
            if params is None:
                c.execute(query)
            else:
                if many:
                    c.executemany(query, params)
                else:
                    c.execute(query, params)
            out = c.fetchall() if read else None
        return out

    def _execute_sql(self, query, params=None):
        return self._sql(query, read=False, params=params, many=False)

    def _executemany_sql(self, query, params=None):
        return self._sql(query, read=False, params=params, many=True)

    def _read_sql(self, query, params=None):
        return self._sql(query, read=True, params=params, many=False)

    def setup(self, vocabname: str, input_words: list, dbfile: str, answer_words: list=None):
        self.vocabname = vocabname


        