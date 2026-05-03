## 4.5.2 Pre-Training Method for Embedding

In order to solve the problem of the huge training cost in the embedding layer, the training of embedding is often performed independently of the deep learning network. After the dense representation of the sparse features is obtained, it is then fed into the neural network together with other features for training the deep learning network.

A typical model using the embedding pre-training method is the FNN model introduced in Section 3.7. This uses each feature latent vector obtained by the FM model training as the initialization weight of the embedding layer, thereby accelerating the convergence speed of the entire network.

In the original implementation of the FNN model, the entire gradient descent process will still update the weight of the embedding. If you want to further speed up the convergence speed of the network, you can also fix the weight of the embedding layer and only update the weight of the upper neural network, which makes the training efficient.

To  extend this, the idea of embedding  is to establish a  mapping  from high-dimensional vectors to  low-dimensional  vectors.  The  mapping  method  is  not limited to neural networks, but can be any heterogeneous model. For example, in the

GBDT+LR combination model introduced in Section 2.6, the GBDT part is essentially an embedding operation. The GBDT model is used to complete the embedding pre-training, and then the generated embedding vectors are input into the single-layer neural network (that is, logistic regression) for CTR prediction.

Since 2015, with the development of graph embedding technology, the expressivity of embedding itself has been further enhanced, and all kinds of supplementary information can be integrated into embedding. This makes embedding a very valuable feature of recommender systems. Usually, the training process of graph embedding can only be performed independently of the recommendation model, which makes the pre-training approach a more popular embedding training practice in the field of deep learning recommender systems.

It is true that separating the embedding training from the training process of the deep neural network will lead to loss of information but the independence of the training process also brings an improvement of training flexibility. For   example, the   embedding of an item or user is relatively stable, since the user's interest and the   attributes of the item usually do not change dramatically within a few days. So the embedding model refreshing does not need to be very high, and can even be as low as weekly. However, in order to grasp the latest overall trend in the data as soon as possible, the upper-layer neural network often requires more frequent training or even online learning. Using different training frequencies to update the embedding model and the neural network model is the optimal solution after a trade-off between training overhead and model freshness.

