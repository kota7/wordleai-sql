# -*- coding: utf-8 -*-

"""
Bigquery backend.

Tables are stored in the following structure:

{project}.{vocabname}.words   : contains all words
{project}.{vocabname}.judges  : contains judge results for all word pairs

i.e. {vocabname} corresponds to the dataset name
"""

import time
import math
import random
from logging import getLogger
logger = getLogger(__name__)

try:
    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound, Forbidden
    #from google.cloud.bigquery import dbapi
except (ModuleNotFoundError, ImportError) as e:
    raise RuntimeError("Import failed: '{}'. Please install bigquery module by `pip install google-cloud-bigquery`".format(e))

from .utils import _timereport, WordEvaluation, _read_vocabfile, _dedup
from .sqlite import WordleAISQLite

def _make_client(credential_jsonfile: str=None, **kwargs):
    if credential_jsonfile is None:
        return bigquery.client.Client(**kwargs)
    else:
        return bigquery.client.Client.from_service_account_json(credential_jsonfile, **kwargs)

def _create_dataset(client: bigquery.Client, datasetname: str, location: str=None):
    dataset = bigquery.dataset.Dataset(client.dataset(datasetname))
    if location is not None:
        dataset.location = location
    return client.create_dataset(dataset, exists_ok=True)

def _setup(client: bigquery.Client, vocabname: str, words: list, project: str=None, location: str="US", partition_size: int=200):
    assert len(words) == len(set(words)), "input_words must be unique"
    wordlens = set(len(w) for w in words)
    assert len(wordlens) == 1, "word length must be equal, but '{}'".format(wordlens)

    if project is None:
        project = client.project
    if location is None:
        location = client.location
    logger.info("Bigquery project: '%s', location: '%s'", project, location)
    
    logger.info("Creating dataset '%s'", vocabname)
    dataset = _create_dataset(client, vocabname, location=location)
    #print(dataset)
    #print(vars(dataset))

    schema = [bigquery.SchemaField("word", "STRING", mode="REQUIRED"),
              bigquery.SchemaField("partid", "INTEGER", mode="REQUIRED")]
    tableid = "{}.{}.words".format(project, vocabname)
    table = bigquery.Table(tableid, schema=schema)

    logger.info("Deleting table 'words' (if exists)")
    client.delete_table(table, not_found_ok=True)    
    logger.info("Creating table 'words'")
    table = client.create_table(table)
    # we assign partition ID to each word
    #client.query('CREATE OR REPLACE TABLE {project}.{dataset}.words (word STRING, partid INTEGER)'.format(project=project, dataset=vocabname)).result()
    rows = [(w, i % partition_size) for i, w in enumerate(words)]
    min_partid = 0
    max_partid = max(row[1] for row in rows)
    # it can take some time until table is found
    time.sleep(20)
    logger.info("Inserting data to table 'words'")
    for i in range(100):
        try:
            client.insert_rows(table, rows)
            logger.info("Inserted data to table 'words'")
            break
        except (NotFound, Forbidden) as e:
            logger.info("Insert to the table 'words' failed (trial %s, %s)", i+1, e)
            time.sleep(15)
    #client.query('DELETE FROM `{project}.{dataset}.words`'.format(project=project, dataset=vocabname)).result()
    

    #client.query('INSERT INTO `{project}.{dataset}.words VALUES (?,?)')
    # time.sleep(15)  # there is some lag before we can insert rows
    # for i in range(20):
    #     try:
    #         client.insert_rows(table, rows)
    #         break
    #     except Exception as e:
    #         print(type(e))
    #         logger.info("Insert failed ('%s') at the try %d", e, i+1)
    #         time.sleep(10)

    # create UDF
    js = """
    // (input_word, answer_word) --> int

    var n_letter = input_word.length;
    // check exact match
    var exact_match = Array(n_letter);
    for (let i=0; i<n_letter; i++) {
        exact_match[i] = (input_word[i]==answer_word[i]);
    }

    // letter count except for the exact math
    var letter_count = {}
    for (let i=0; i<n_letter; i++) {
        if (exact_match[i]) continue;
        if (answer_word[i] in letter_count) {
            letter_count[answer_word[i]]++;
        } else {
            letter_count[answer_word[i]] = 1;
        }
    }

    // define partial match
    var partial_match = Array.from({length: n_letter}, i => false);
    for (let i=0; i<n_letter; i++) {
        if (exact_match[i]) continue;
        if (input_word[i] in letter_count) {
            partial_match[i] = true;
            letter_count[input_word[i]]--;
        } 
    }

    var out = 0;
    var power = 1;
    for (let i=0; i<n_letter; i++) {
        if (exact_match[n_letter-1-i]) {
            out += (power * 2);
        } else if (partial_match[n_letter-1-i]) {
            out += power;
        }
        power *= 3;
    }  
    return out;  
    """
    q = '''
    CREATE FUNCTION IF NOT EXISTS `{project}.{dataset}.WordleJudge` (input_word STRING, answer_word STRING)
      RETURNS INTEGER
      LANGUAGE js AS """{js}""";
    '''.format(project=project, dataset=vocabname, js=js)    
    logger.info("Creating udf 'WordleJudge'")    
    client.query(q).result()

    with _timereport("precomputing wordle judges"):
        # client.query('''
        # DROP TABLE IF EXISTS {project}.{dataset}.judges
        # '''.format(project=project, dataset=vocabname)).result()
        
        q = '''
        CREATE OR REPLACE TABLE {project}.{dataset}.judges
          PARTITION BY RANGE_BUCKET(answer_word_partid, GENERATE_ARRAY({min_partid}, {max_partid}))
          CLUSTER BY input_word, judge
        AS
          SELECT
            a.word AS input_word,
            b.word AS answer_word,
            {project}.{dataset}.WordleJudge(a.word, b.word) AS judge,
            b.partid AS answer_word_partid
          FROM
            {project}.{dataset}.words AS a, {project}.{dataset}.words AS b
        '''.format(project=project, dataset=vocabname, min_partid=min_partid, max_partid=max_partid+1)
        job = client.query(q)
        job.result()
        logger.info("Total bytes processed: %.2f GB, total bytes billed: %.2f GB",
                    1.0*job.total_bytes_processed/1073741824, 1.0*job.total_bytes_billed/1073741824)

def _evaluate(client: bigquery.Client, vocabname: str, project: str,
              top_k: int=20, criterion: str="mean_entropy", candidates: list=None)-> list:
    # find the number of all words and compare with the number of candidates
    # if they are the same, then we do not need to filter answer_word
    job = client.query('SELECT count(*) FROM {project}.{dataset}.words'.format(project=project, dataset=vocabname))
    rows = job.result()    
    n_words = next(rows)[0]

    if candidates is None or len(candidates) >= n_words:  # all words are in the candidates
        params = None
        answer_filter = ""
    else:
        candidate_set = set(candidates)
        params = [bigquery.ScalarQueryParameter(None, "STRING", c) for c in candidate_set]
        answer_filter = """
        WHERE
          answer_word_partid IN (SELECT partid FROM {project}.{dataset}.words WHERE word IN ({placeholder}))
          AND
          answer_word IN ({placeholder}) 
        """.format(project=project, dataset=vocabname, placeholder=",".join("?" * len(params)))
        params = params + params
        # answer_filter = """
        # INNER JOIN
        #   {project}.{dataset}.words AS b
        #   ON
        #     b.word IN ({placeholder})
        #     AND a.answer_word_partid = b.partid
        #     AND a.answer_word = b.word          
        # """.format(project=project, dataset=vocabname, placeholder=",".join("?" * len(params)))
        # params = params
        # # join version costs more we go with the IN version above
    q = """
    with tmp AS (
      SELECT
        input_word,
        judge,
        count(*) AS n,
        log(count(*), 2) AS entropy
      FROM
        {project}.{dataset}.judges
      {answerfilter}
      GROUP BY
        input_word, judge
    )
    SELECT
      input_word,
      max(n) AS max_n,
      1.0 * sum(n*n) / sum(n) AS mean_n,
      sum(n*entropy) / sum(n) AS mean_entropy
    FROM
      tmp
    GROUP BY
      input_word
    """.format(answerfilter=answer_filter, project=project, dataset=vocabname)
    #print(q)
    #print(params)
    if params is None:
        job = client.query(q)
    else:
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(q, job_config=job_config)
    rows = job.result()
    #print(job.total_bytes_processed)
    #print(job.total_bytes_billed)
    logger.info("Total bytes processed: %.2f GB, total bytes billed: %.2f GB",
                1.0*job.total_bytes_processed/1073741824, 1.0*job.total_bytes_billed/1073741824)
    # with _connect(client) as conn:
    #     c = conn.cursor()
    #     if params is None:
    #         c.execute(q)
    #     else:
    #         c.execute(q, params)
    candidate_set = None if candidates is None else set(candidates)
    out = [tuple(row) for row in rows]
    out = [row + (1 if candidate_set is None else int(row[0] in candidate_set),) for row in out]
    out = [WordEvaluation(*row) for row in out]
    out.sort(key=lambda row: (getattr(row, criterion), -row.is_candidate))
    return out[:top_k]

def _vocabnames(client: bigquery.Client, project: str)-> list:
    # return datasets that includes words and judges table
    datasets = client.list_datasets(project=project)
    out = []
    for d in datasets:
        tables = client.list_tables(d)
        tableids = set(t.table_id for t in tables)
        if "words" in tableids and "judges" in tableids:
            out.append(d.dataset_id)
    return out

def _words(client: bigquery.Client, vocabname: str, project: str)-> list:
    job = client.query('SELECT word FROM `{project}.{dataset}.words`'.format(project=project, dataset=vocabname))
    rows = job.result()
    words = [row[0] for row in rows]
    return words

class WordleAIBigquery(WordleAISQLite):
    """
    Wordle AI with SQLite backend

    Vocab information is stored in {vocabname}_words and {vocabname}_judges

    Args:
        vocabname (str):
            Name of vocaburary
        words (str of list): 
            If str, the path to a vocabulary file
            If list, the list of words
            Can be omitted if the vocabname is already in the database and resetup=False
        credential_jsonfile (str):
            Path to the service accound credential file
            If not supplied, authenticate with no file
        project (str):
            GCP project id to use
            If not supplied, use the default project of the client
        location (str):
            Location of the bigquery tables
        partition_size (int):
            Partition size of judges table
            The rows of judges table are partitioned by a set of answer_word
            both for cost reduction and computaion speed

        decision_metric (str):
            The criteria to pick a word
            Either 'max_n', 'mean_n', of 'mean_entropy'
        candidate_weight (float):
            The weight added to the answer candidate word when picking a word
        strength (float):
            AI strength in [0, 10]

        resetup (bool):
            Setup again if the vocabname already exists        
    """
    def __init__(self, vocabname: str, words: list or str=None,
                 credential_jsonfile: str=None, project: str=None, location: str="US", partition_size: int=200,
                 decision_metric: str="mean_entropy", candidate_weight: float=0.3, strength: float=6,
                 resetup: bool=False, **kwargs):
        self.client = _make_client(credential_jsonfile, project=project, location=location)
        self.project = self.client.project
        self.location = self.client.location
        logger.info("GCP project: '%s', location: '%s'", self.project, self.location)

        self.vocabname = vocabname
        self.decision_metric = decision_metric
        self.candidate_weight = candidate_weight
        self.strength = min(max(strength, 0), 10)  # clip to [0, 10]
        # strength is linearly converted to the power of noise: 0 -> +5, 10 -> -5
        # larger noise, close to random decision
        self.decision_noise = math.pow(10, 5-self.strength)

        if resetup or vocabname not in self.vocabnames:
            assert words is not None, "`words` must be supplied to setup the vocab '{}'".format(vocabname)
            words = _read_vocabfile(words) if type(words) == str else _dedup(words)
            with _timereport("Setup tables for vocabname '%s'" % vocabname):
                _setup(client=self.client, vocabname=self.vocabname, words=words,
                       project=self.project, location=self.location, partition_size=partition_size)
        #self.set_candidates()
        self._info = []                  # infomation of the judge results
        self._nonanswer_words = set([])  # words that cannot become an answer

    @property
    def name(self)-> str:
        return "Wordle AI (bigquery backend)"

    @property
    def vocabnames(self)-> list:
        """Available vocab names"""
        return _vocabnames(client=self.client, project=self.project)

    @property
    def words(self)-> set:
        """All words that can be inputted"""
        return _words(client=self.client, vocabname=self.vocabname, project=self.project)
    
    def evaluate(self, top_k: int=20, criterion: str="mean_entropy")-> list:
        """
        Evaluate input words and return the top ones in accordance with the given criterion
        """
        return _evaluate(self.client, self.vocabname, self.project,
                         top_k=top_k, criterion=criterion, candidates=self.candidates)