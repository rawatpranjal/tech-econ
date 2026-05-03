## 4.3.1 Fundamentals of Item2vec

As mentioned in the matrix factorization section (Section 2.3), the user latent vector and the item latent vector are generated through matrix decomposition. Viewing the matrix factorization model from the perspective of embedding, the user latent vector and the item latent vector are one type of user embedding vector and item embedding vector, respectively. Due to the popularity of Word2vec, more and more embedding methods can be directly used to generate item embedding vectors, while user embedding vectors are more often calculated by averaging or clustering item embeddings in the user's action history. Using the similarity between the user vector  and the item vector, the candidate set can be quickly obtained directly in the retrieval layer of the recommender system, or directly used in the ranking layer to get the final recommendation list. Following this idea, Microsoft proposed a method, Item2vec, to calculate the embedding vector of items in 2016.

Compared with Word2vec, which uses word sequence to generate the embedding vectors, Item2vec utilizes the sequence of actions from a user's browsing, purchasing, and other histories.

Assuming that a sentence of length T in Word2vec model is w w wT 1 2 , , , … , the loss function can be expressed as shown in Eq. 4.1. Similarly, assuming the user's action sequence of length K is /g90 /g90 /g90 1 2 , , , /g125 K , the loss function of Item2vec is then as follows,

<!-- formula-not-decoded -->

Neural

Network

User Features

Dot Product

By comparing the difference between Eqs. 4.1 and 4.4, it can be found that the only difference  between  Item2vec  and  Word2vec  is  that  Item2vec  abandons  the  concept of time window and considers that any two items in the sequence are related. Therefore,  in  the  loss  function  of  Item2vec  (Eq.  4.4),  the  loss  is  the  sum  of  the log probabilities of item pairs, instead of the log probabilities of items within the time window.

After  the  optimization  target  is  defined,  the  remaining  training  process  of Item2vec  and  the  generation  process  of  the  final  item  embedding  are  consistent with Word2vec. The lookup table of the final item vector is analogical to the lookup table of the word vector in Word2vec. Readers can refer to the relevant content of Word2vec in Section 4.2 for more training details.

