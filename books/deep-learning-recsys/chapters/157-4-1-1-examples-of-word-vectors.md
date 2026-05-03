## 4.1.1 Examples of Word Vectors

The popularity of the embedding method started from research on the problem of word vectors in the field of natural language processing. Here we take the word vector as an example to further explain the meaning of embedding.

Figure  4.1(a)  shows  the  mappings  of  the  embedding  vectors  of  several  words (with  implicit  relationships  on  genders)  encoded  by  the  Word2vec  method  in  the embedding space. It can be seen that the distance vector from Embedding(king) to Embedding(queen) is parallel with that from Embedding(man) to Embedding(woman). This  example  indicates  that  the  operation  between  word  embedding  vectors  can even contain semantic-relationship information between words. Similarly, the partof-speech  example  shown  in  Figure  4.1(b)  also  reflects  this  feature  of  word  vectors.  The  distance  vectors  from  Embedding(walking)  to  Embedding(walked)  and Embedding(swimming) to Embedding(swam) are similar,  which  indicates  that  the part-of-speech relationship between walking-walked and swimming-swam is similar.

Under  the  premise  of  a  large  amount  of  corpus  input,  embedding  technology  can  even  mine  some  more  general  knowledge.  As  shown  in  Figure  4.1(c), Embedding Madrid Embedding Spain Embedding Beijing Embe ( ) ( ) ( ) /g16 /g124 /g16 dding (China). This  shows  that  the  operation  between  embeddings  can  mine  general  relational knowledge like 'capital-country.'

From these examples, it is clear that in the word vector space, even if the word vector is not known at all, it can still be inferred by the semantic relationship and the word vector operation. This is how embedding describes the items in a specific vector space and at the same time reveals the potential relationship between items. In a sense, the embedding method even has an ontological and philosophical significance.

