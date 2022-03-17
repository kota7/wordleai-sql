WORDLE AI with SQL Backend
==========================
[![](https://badge.fury.io/py/wordleaisql.svg)](https://badge.fury.io/py/wordleaisql)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/kota7/wordleai-sql/main/streamlit/app.py)

This package provides an [Worldle]((https://www.nytimes.com/games/wordle/index.html)) solver with SQL backend.

## How to use

```shell
# Install this library via PyPI
pip install wordleaisql
# Then run the executable that comes with the library
wordleai-sql

# Alternatively, clone this repository and run without pip-install
python wordleai-sql.py
```


## Solver session example

```shell
$ wordleai-sql

Hi, this is Wordle AI (SQLite backend, approx).

12947 remaining candidates: ['cigar', 'rebut', 'sissy', 'humph', 'awake', 'blush', 'focal', 'evade', 'naval', 'serve', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word (<criterion> is optional)
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> s
[INFO] Start AI evaluation (2022-03-09 00:37:13)
[INFO] End AI evaluation (2022-03-09 00:37:18, elapsed: 0:00:04.153101)
* Top 20 candidates ordered by mean_entropy
--------------------------------------------------------------------
  input_word         max_n        mean_n  mean_entropy  is_candidate
--------------------------------------------------------------------
       reais            30          12.0         3.094             1
       laers            33          13.5         3.218             1
       aeons            35          14.2         3.312             1
       races            32          14.4         3.323             1
       leads            34          15.1         3.349             1
       strae            33          14.8         3.376             1
       lines            43          16.4         3.386             1
       soral            35          15.6         3.427             1
       cries            48          17.4         3.429             1
       scrae            34          16.2         3.471             1
       rules            42          17.2         3.478             1
       oared            41          17.9         3.511             1
       losen            52          17.9         3.515             1
       sedan            40          17.6         3.516             1
       sured            52          19.1         3.546             1
       artis            45          19.4         3.547             1
       least            42          18.7         3.549             1
       stire            46          18.5         3.552             1
       stria            49          19.3         3.556             1
       nails            55          18.7         3.557             1
--------------------------------------------------------------------
12947 remaining candidates: ['cigar', 'rebut', 'sissy', 'humph', 'awake', 'blush', 'focal', 'evade', 'naval', 'serve', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word (<criterion> is optional)
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> u races 00000
896 remaining candidates: ['humph', 'outdo', 'digit', 'pound', 'booby', 'loopy', 'lying', 'moult', 'guild', 'thumb', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word (<criterion> is optional)
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> s
[INFO] Start AI evaluation (2022-03-09 00:37:35)
[INFO] End AI evaluation (2022-03-09 00:37:39, elapsed: 0:00:03.439437)
* Top 20 candidates ordered by mean_entropy
--------------------------------------------------------------------
  input_word         max_n        mean_n  mean_entropy  is_candidate
--------------------------------------------------------------------
       monty            41          16.8         3.454             1
       gipon            66          20.5         3.546             1
       lofty            53          20.0         3.686             1
       bilgy            70          24.2         3.746             1
       bundt            69          23.2         3.779             1
       limbo            69          23.6         3.780             1
       bundy            63          23.5         3.782             1
       found            56          23.7         3.816             1
       youth            50          22.6         3.827             1
       joint            65          23.9         3.895             1
       downy            61          25.5         3.902             1
       milko            78          27.5         3.924             1
       fungo            86          29.6         3.926             1
       lumbi            77          29.1         3.976             1
       tupik            68          28.0         3.981             1
       goopy            76          28.3         4.012             1
       jolty            59          24.3         4.015             1
       muhly            65          28.1         4.034             1
       nouny            59          25.0         4.041             1
       touzy            49          25.0         4.066             1
--------------------------------------------------------------------
896 remaining candidates: ['humph', 'outdo', 'digit', 'pound', 'booby', 'loopy', 'lying', 'moult', 'guild', 'thumb', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word (<criterion> is optional)
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> u monty 22220
'month' should be the answer!
Thank you!
```

## Suggestion criteria

Input words are evaludated by the three criteria as follows: 

- "max_n": Maximum number of the candidate words that would remain.
- "mean_n": Average number of the candidate words that would remain.
- "mean_entropy": Average of the log2 of number of the candidate words that would remain.

Note that if there are `n` candidate words with the equal probability, then probability of each word `i` is `p_i = 1/n`.
Then, the entropy is given by `-sum(p_i log2(p_i)) = - n * (1/n) log2(1/n) = log2(n)`.
Hence, the average of `log2(n)` can be seen as the average entropy.

"mean_entropy" is often used in practice and thus set as the default choice of the program.
"max_n" can be seen as a pessimistic criterion since it reacts to the worst case.
"mean_n" can seem an intutive criterion but does not work as well as "mean_entropy" perhaps due to the skewed distribution.

See also the simulation results for a comparison of the criteria (notebook at [simulation/simulation-summary.ipynb](simulation/simulation-summary.ipynb) or view on [nbviewer](https://nbviewer.org/github/kota7/wordleai-sql/blob/main/simulation/simulation-summary.ipynb)).


## Play and challenge mode

- By default, `wordleai-sql` command starts an interactive solver session.
- `wordleai-sql --play` starts a self-play game.
- `wordleai-sql --challenge` starts a competition against an AI.
- In the play and challenge mode, the answer word is chosen in accordance with the answer weight by default. One can set `--no_answer_weight` option to make all words potentially become an answer word.


## Using a custom word set

- The default word list is at [wordleaisql/vocab/wordle-vocab.txt](wordleaisql/vocab/wordle-vocab.txt). The list perhaps is compatible with [New York Times version](https://www.nytimes.com/games/wordle/index.html).
- One may use a custom word list by specifying `--vocabfile=<file path>` option.
  - A file should contain words of the same length, separated by the line break ("\n").
  - Each line may contain a nonnegative numeric value separated by a space, which is used as the relative probability that this word is chosen as the answer (in play and challenge mode). If not supecified, the word is given the weight one.
  - A file can be gzip compressed, where the filename must end with ".gz". 
  - Although not tested thoroughly, the program would work with words containing multibyte characters (with utf8 encoding) or digits.
- By default, the file name without extension is used as the `vocabname`. One may change this by `--vocabname`.
- See `vocab-examples/` folder for some examples.

```shell
# Example
wordleai-sql --vocabname myvocab --vocabfile my-vocab.txt
```


## Backend options

### SQLite with approximate evaluation (default)

```shell
wordleai-sql -b approx
```

- With `-b approx` option, we employ approximate evaluation of words by sampling input and/or answer words.
- The database setup completes quikckly since this does not require precompuation of the judge results.
- Evaluation also completes quickly since small numbers of input and/or answer words are involved in the calculation.
- Although approximate, the engine tends to provide close-to-optimal suggestions thanks to the law of large numbers.

### SQLite with full evaluation

```shell
wordleai-sql -b sqlite
```

- This engine evaluates all words using the all answer candidates.
- To enhance the calculation the engine precomputes all judge results for all word pairs on the setup.
  - The file size becomes about 8.4GB.
  - The process may take about an hour, depending on the CPU speed.
  - The time for the setup will be significantly reduced if c++ compiler command (e.g `g++` or `clang++`) is available.

### Google bigquery backend

```shell
# --vocabname is used as the dataset name
wordleai-sql -bbq --bq_credential "gcp_credentials.json" --vocabname "wordle_dataset"
```

- With `-bbq` option, we employ google bigquery as the backend SQL engine.
- We need to supply a credential json file of the GCP service account with the following permissions:
  ```
  bigquery.datasets.create
  bigquery.datasets.get
  bigquery.jobs.create
  bigquery.jobs.get
  bigquery.routines.create
  bigquery.routines.delete
  bigquery.routines.get
  bigquery.routines.update
  bigquery.tables.create
  bigquery.tables.delete
  bigquery.tables.get
  bigquery.tables.getData
  bigquery.tables.list
  bigquery.tables.update
  bigquery.tables.updateData
  ```

## Other options

See `wordleai-sql -h` for other options, which should mostly be self-explanatory.


## GUI application

- A browser application built on [streamlit](https://streamlit.io/) is at [streamlit/app.py](streamlit/app.py). This can be run with the following command:
  ```shell
  # install dependencies if not
  pip install pandas streamlit
  streamlit run ./streamlit/app.py
  ```
- The app is also deployed on the [streamlit cloud](https://share.streamlit.io/kota7/wordleai-sql/main/streamlit/app.py).
