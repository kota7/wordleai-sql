WORDLE AI with SQL Backend
==========================

## Usage

```shell
# Install the library with pip
pip install -U wordleaisql
# Then run the executable that comes with the library
wordleai-sql

# Alternatively, clone this repository and simply run
python wordleaisql/wordleai.py
```

Note.
- The program creates a SQLite file named "wordle-ai.db" in the working directory, whose size typically is about 8.4GB.
- For the first run, it will take a while to set up the database.
- The setup time will be significantly reduced if c++ compiler command (`g++` or `clang++`) is available.


## Session example

```shell
Hello! This is Wordle AI with SQLite backend.

12947 remaining candidates: ['yarco', 'knars', 'loamy', 'barps', 'dozed', 'yerks',
'reggo', 'rowth', 'spoom', 'rewin', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> s
Start evaluating candidates (2022-02-21 20:59:06.659721)
End evaluating candidates (2022-02-21 20:59:22.748949, elapsed: 0:00:16.089228)
* Top 20 candidates ordered by mean_entropy
--------------------------------------------------------------------
  input_word         max_n        mean_n  mean_entropy  is_candidate
--------------------------------------------------------------------
       tares           856         301.3         7.464             1
       lares           830         287.7         7.509             1
       rales           830         291.0         7.544             1
       rates           856         310.2         7.562             1
       teras           856         335.8         7.582             1
       nares           822         304.5         7.592             1
       soare           767         302.9         7.598             1
       tales           864         324.4         7.604             1
       reais           766         303.7         7.609             1
       tears           856         348.4         7.627             1
       arles           830         313.6         7.629             1
       tores          1098         357.0         7.640             1
       salet           864         332.5         7.642             1
       aeros           799         308.9         7.646             1
       dares           985         351.2         7.649             1
       reals           830         327.8         7.660             1
       saner           837         316.9         7.660             1
       lears           830         330.2         7.671             1
       lores           983         338.9         7.683             1
       serai           695         314.2         7.685             1
--------------------------------------------------------------------
12947 remaining candidates: ['yarco', 'knars', 'loamy', 'barps', 'dozed', 'yerks',
'reggo', 'rowth', 'spoom', 'rewin', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> u tares 10120
38 remaining candidates: ['inter', 'noter', 'ether', 'voter', 'roted', 'citer',
'luter', 'enter', 'oxter', 'cruet', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> s
Start evaluating candidates (2022-02-21 20:59:30.849712)
End evaluating candidates (2022-02-21 20:59:32.386516, elapsed: 0:00:01.536804)
* Top 20 candidates ordered by mean_entropy
--------------------------------------------------------------------
  input_word         max_n        mean_n  mean_entropy  is_candidate
--------------------------------------------------------------------
       notum             8           4.2         1.691             0
       ontic             8           4.6         1.843             0
       mount             8           4.5         1.859             0
       motif             7           4.4         1.860             0
       moult            10           4.9         1.874             0
       muton             8           4.7         1.893             0
       potin             8           4.7         1.895             0
       lotic             8           4.7         1.914             0
       onium             8           4.7         1.914             0
       mohur             9           4.7         1.916             0
       optic             7           4.7         1.916             0
       minor             8           4.8         1.925             0
       humor             9           5.1         1.939             0
       pitot             7           5.1         1.960             0
       rutin             9           4.8         1.993             0
       milor             9           5.1         1.994             0
       piton             8           5.3         2.024             0
       oubit             7           4.7         2.027             0
       point             8           5.1         2.040             0
       opium             8           5.2         2.042             0
--------------------------------------------------------------------
38 remaining candidates: ['inter', 'noter', 'ether', 'voter', 'roted', 'citer',
'luter', 'enter', 'oxter', 'cruet', '...']

Type:
  '[s]uggest <criterion>'     to let AI suggest a word
  '[u]pdate <word> <result>'  to provide new information
  '[e]xit'                    to finish the session

where
  <criterion>  is either 'max_n', 'mean_n', or 'mean_entropy'
  <result>     is a string of 0 (no match), 1 (partial match), and 2 (exact match)

> u notum 01100
'other' should be the answer!

Thank you!
```

## Suggestion criteria

There are three criteria for the candidate evaluation: 

- "max_n": Maximum number of the candidate words that would remain.
- "mean_n": Average number of the candidate words that would remain.
- "mean_entropy": Average of the log2 of number of the candidate words that would remain.

Note that if there are `n` candidate words with the equal probability, then probability of each word `i` is `p_i = 1/n`.
Then, the entropy is given by `-sum(p_i log2(p_i)) = - n * (1/n) log2(1/n) = log2(n)`.
Hence, the average of `log2(n)` would be the average entropy.

"mean_entropy" is often used in practice and thus set as the default choice of the program.
"max_n" can be seen as a pessimistic criterion since it reacts to the worst case.
"mean_n" can seem an intutive criterion but does not work as well as "mean_entropy" perhaps due to the skewed distribution.

## Using a custom answer set

- By default, the program uses "vocab.txt" as the word candidate list, which perhaps is compatible with [New York Times version](https://www.nytimes.com/games/wordle/index.html)
- You may give a different list with `--vocabfile` option. You should also specify `--dbfile` option other than the default ("wordle-ai.db") because the database setup would be overwritten.
- The file should contain words of the same length, separated by the line break ("\n").
- Although not tested, the program would work with words containing multibyte characters (with utf8 encoding) or digits.

```shell
# Example
wordleai-sql --dbfile custom-wordle.db --vocabfile my-vocab.txt
# or 
python wordleai.py --dbfile custom-wordle.db --vocabfile my-vocab.txt
```

## Play and challenge mode

- `wordleai-sql --play` starts a self-play game.
- `wordleai-sql --challenge` starts a competition against an AI.


## Other options

See `wordleai-sql -h` or `python wordleai.py -h` for other options, which should mostly be self-explanatory.
