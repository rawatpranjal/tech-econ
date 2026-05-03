## 6.5.1 Pre-Stored Recommendation Results or Embeddings

For online serving of the recommendation model, the simplest and most straightforward method is to generate the recommendation results of each user in an offline environment, and then pre-store the results in an online database such as Redis. You can directly extract the pre-stored data in the online environment and recommend it to the user online. The pros and cons of this method are obvious. The pros are as follows:

- (1)  There is no need to implement the process of model online inference. The offline training platform is completely decoupled from the online service platform, and any offline machine learning tool can be flexibly selected for model training.
- (2)  There is no complicated calculation in the online service process, so the online latency of the recommender system is extremely low.

The cons of this method are as follows:

- (1)  It needs to store the recommendation results for the combinations of users, items and application scenarios. When the number of users and items is very large, it can easily encounter combination explosion, and the online database cannot support the storage of such large-scale results.
- (2)  The online contextual features cannot be introduced, so the performance of the recommender system is limited.

Considering  these  pros  and  cons,  the  method  of  directly  storing  recommendation results is usually adopted only for small user scales, or some special application scenarios such as cold start and popular lists.

Pre-computing and storing the embeddings for user and item is another way to replace online inferencing with stored data. Compared with directly storing the recommendation results, the method of storing embeddings greatly reduces the amount of storage. It only needs to conduct the inner product or cosine similarity operation to obtain the final recommendation result online, which is a method that is often used in the industry to deploy the model.

This method cannot support the introduction of online contextual features, and cannot perform online inference by complex model. As a result, the expressivity of the recommendations is limited. Therefore, complex models still require a recommender system capable of online inferencing.

