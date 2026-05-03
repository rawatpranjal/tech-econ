## 4.5 Integration of Embedding and Deep Learning Recommender Systems

We have introduced the principles and development process of embedding. But in the real implementation of recommender systems, embedding needs to integrate with other parts of the deep learning network to complete the whole recommendation process. As an integral part of the deep learning recommender systems, embedding technology is mainly used in the following three ways:

- (1)  As an embedding layer in the deep learning network, it converts the input features from high-dimensional sparse vectors to low-dimensional dense feature vectors;
- (2)  As a pre-trained embedding feature vector, after connecting with other feature vectors, it can serve as an input to the deep learning network for training;
- (3)  By  calculating  the  similarity  between  user  embedding  and  item  embedding, embedding can be directly used as one of the retrieval layers or retrieval strategies of the recommender system.

In this chapter, we will describe the detailed methods for combining embedding and deep learning recommender systems.

