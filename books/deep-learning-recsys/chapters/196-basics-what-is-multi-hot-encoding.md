## Basics: What Is Multi-Hot Encoding?

For data such as historical behavior and label features, users often interact with multiple items, or are labeled with multiple tags of the same category. In this case, the most commonly used method is multi-hot encoding.

For example, an e-commerce website has a total of 10 000 products, and the user  has  purchased  10  of  them,  then  the  user's  historical  behavior  data  can  be converted into a 10 000-dimensional numerical vector, of which only 10 of the purchased products correspond to the dimension of 1, the other dimensions are 0. This is multi-hot encoding.

in detail. On the basis of one-hot encoding, when encountered with multiple category selections for the same feature, multi-hot encoding can also be used.

The main problems of one-hot or multi-hot encoding of categorical features are that the dimension of the feature vectors is too large, the features are too sparse. This can easily lead to underfitting of the model, and the model has too many weight parameters,  which  leads  to  slow  convergence  of  the  model.  Therefore,  with  the maturity of the embedding technology, it is widely used in the processing of categorical  features.  The  categorical  features  are  firstly  encoded  into  dense  embedding vectors, and then combined with other features to form the final input feature vectors.

