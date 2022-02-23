#include <iostream>
#include <string>
#include <vector>
#include <cassert>
#include <map>

/*
Calculate wordle responses of all word pairs

Input (standard input): 
  N WORD_1 WORD_2 WORD_3 .... WORD_N

Output (standard output):
  WORD_1 WORD_1 RESULT_{1,1}
  WORD_1 WORD_2 RESULT_{1,2}
  WORD_1 WORD_3 RESULT_{1,3}
  ....
  WORD_N WORD_N RESULT_{N,N}

Compile command example
  g++ -Wall -Werr -O3 wordle-all-pairs.cpp
*/

int wordle_response(std::string input_word, std::string answer_word) {
  size_t n1 = input_word.size();
  size_t n2 = answer_word.size();
  assert (n1==n2);

  //std::cerr << "Checking for exact match\n";
  // check for the exact match
  std::vector<bool> exact_match(n1, false);
  for (size_t i=0; i<n1; i++) {
    if (input_word[i]==answer_word[i]) exact_match[i] = true;
  }
  
  //std::cerr << "Counting letters in answer word\n";
  // count letters if not exact match
  std::map<char, size_t> letter_count;
  for (size_t i=0; i<n1; i++) {
    if (exact_match[i]) continue;
    if (letter_count.find(answer_word[i])==letter_count.end()) {
      // key not in the map
      letter_count.insert(std::make_pair(answer_word[i], 1));
    } else {
      letter_count[answer_word[i]]++;  
    }    
  }
  
  //std::cerr << "Checking for the partial match\n";
  // check for the partial match
  std::vector<bool> partial_match(n1, false);
  for (size_t i=0; i<n1; i++) {
    if (exact_match[i]) continue;
    if (letter_count.find(input_word[i])==letter_count.end()) continue;
    if (letter_count[input_word[i]]>0) {
      partial_match[i] = true;
      letter_count[input_word[i]]--;
    }
  }
  /*
  for (int i=0; i<n1; i++) std::cout << exact_match[i] << " "; 
  std::cout << "\n";
  for (int i=0; i<n1; i++) std::cout << partial_match[i] << " "; 
  std::cout << "\n";
  */

  //std::cerr << "Compiling output\n";
  // compile output
  int power = 1;
  int out = 0;
  for (size_t i=0; i<n1; i++) {
    //std::cerr << i << " ";
    size_t k = n1-1-i;
    if (exact_match[k]) {
      out += (power*2);
    } else if (partial_match[k]) {
      out += power ;
    }
    power *= 3;
  }

  return out;
}


int main() {
  int n;
  std::cin >> n;
  std::vector<std::string> words(n);
  for (int i=0; i<n; i++) std::cin >> words[i];
  
  for (int i=0; i<n; i++) {
    for (int j=0; j<n; j++) {
      //k++;
      int res = wordle_response(words[i], words[j]);
      std::cout << words[i] << ' ' << words[j] << ' ' << res << '\n';
    }
  }

}