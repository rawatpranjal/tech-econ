## 4.2.1 What Is Word2vec?

Word2vec is short for 'word to vector.' As the name suggests, Word2vec is a model that generates a vector representation for words.

In order to train the Word2vec model, a corpus consisting of a set of sentences needs to be prepared. Suppose one of the sentences of length T is w w wT 1 2 , , , … , and assume that each word is closely related to its adjacent word, that is, each word is determined by the adjacent words (the main principle of the continuous bag of words (CBOW) model in Figure 4.2) or determines its adjacent words (the main principle of the Skip-gram model in Figure 4.2). As shown in Figure 4.2, the input of the CBOW model is the words around ω t , and the predicted output is ω t , while Skip-gram is the opposite. Empirically, Skip-gram works better; thus, we will use Skip-gram as the framework to explain the details of the Word2vec model in this section.

