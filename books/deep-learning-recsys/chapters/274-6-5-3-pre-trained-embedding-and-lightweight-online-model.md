## 6.5.3 Pre-Trained Embedding and Lightweight Online Model

Fully adopting a self-developed platform has clear drawbacks, like heavy engineering efforts and poor flexibility. Today, with the rapid evolution of various complex models, the disadvantages of the self-developed model are clearer. Is there any way to combine the flexibility of the general platform, the diversity of functions, and online inferencing efficiency from the self-developed platform? The answer is yes.

Many companies in the industry have adopted a new recommender system design pattern with offline training of complex networks, generating embeddings, and storing them in in-memory databases. A lightweight model such as logistic regression or shallow neural networks is used for online recommendation. The 'two-tower' model introduced in Section 4.3 is a typical example (as shown in Figure 4.5).

The two-tower model uses complex networks to embed the user features and item features, respectively. Before the final cross layer, there is no interaction between the user features and the item features, which forms two independent 'towers.'

After completing the training of the two-tower model, the final user embeddings and item embeddings can be stored in the in-memory database. When performing online inference, there is no need to reproduce the complex network, and only the

logic  of  the  final  output  layer  needs  to  be  implemented.  The  output  layer  here  is mostly logistic regression or softmax or a shallow neural network. But they are all relatively simple to implement. After the user embedding and the item embedding are fetched from the in-memory database, the final prediction can be obtained through the online calculation of the output layer.

With such architecture, some other contextual features can also be used together with user and item embeddings in the final output layer. This enables us to introduce more real-time features and enrich the feature sources of the model.

Nowadays,  when  Graph  Embedding  technology  has  become  very  powerful. The offline training method of embeddings can integrate a large amount of user and item information, and the output layer does not need to be very complicated. Therefore, the method of embedding pre-training plus a lightweight online model is a flexible and simple approach for recommender systems without much impact on the model performance.

