## 2.2.6 The Next Step of Collaborative Filtering

Collaborative filtering is a very intuitive and interpretable model, but it does not generalize very well. In other words, the information of two items that are similar cannot be generalized into the similarity calculation of other items. This leads to a serious problem - popular items have a strong Matthew effect and are likely to be similar to a large number of items; while the tail items are rarely similar to other items due to sparse feature vectors, resulting in very rarely recommended.

For example, choose the vectors of four items A, B, C, and D from a co-occurrence matrix, and use the cosine similarity to calculate the item similarity matrix (as shown in Figure 2.3).

According to the item similarity matrix, the similarity between A, B, and C is 0, and the item most similar to A, B, and C is D. Therefore, in the recommender system based on ItemCF, the item D will be recommended to all users who have had positive feedback on A, B, and C.

But, in fact, the reason that item D is similar to A, B, and C is only because item D is a popular commodity. The main reason why the system cannot find similarity between A, B, and C is that their feature vectors are very sparse and lack the direct data for similarity calculation. This phenomenon reveals the natural defect of CF - the Matthew effect of the recommendation results is obvious, and it lacks the ability to deal with sparse vectors.

Figure 2.3 From item vectors to similarity matrix.

In order to solve these problems and increase the model's generalization ability, the MF technique is proposed. Based on the CF co-occurrence matrix, this method uses denser latent vectors to represent users and items, and mines the implicit interests and features of users and items, which, to a certain extent, makes up for the problem of lacking the ability to deal with sparse matrices in CF models.

In addition, CF only uses the interaction information between users and items and cannot effectively include many other features from users, items, and contexts, such as  user  age,  gender,  product  description,  product  classification,  and  current  time, which undoubtedly results in the loss of important information. In order to include these features into the recommendation model, recommender systems have gradually developed into a machine learning model with LR as the core, so that different types of features can be integrated.

