## 6.6.2 Trade-Off between Redis Capacity and Online Model Deployment

For  online  recommender  systems,  both  model  parameters  and  online  features  are necessary for online model inferencing. In order to ensure real-time performance with low data query latency, many companies use the in-memory database method to  host  the  data.  Among  the  data  storage  solutions,  Redis  has  become  the  mainstream choice. However, Redis needs to take a lot of memory resources, and memory resources are relatively scarce and expensive compared with others. Therefore, whether you use AWS (Amazon Web Services, Amazon Web Services Platform), Alibaba Cloud, or a self-built data center, the cost of using Redis is relatively high, and the capacity of Redis has become a key factor restricting the ways how the recommendation model goes online.

Due to such constraints, engineers must consider the problem from two aspects:

- (1)  The model's parameter scale should be as small as possible. Especially for the deep learning recommendation models, the parameter quantity of the model has been increased by several orders of magnitude compared with the traditional model.
- (2)  The number of features used for online estimation cannot be increased indefinitely, and a certain degree of trade-off should be made based on the feature's importance.

To launch a recommender system under such constraints, it is necessary to drop some unimportant factors and focus on the key points. An experienced engineer's thinking would be like this:

- (1)  If  the  feature  dimensions  are  tens  of  millions  or  even  higher,  theoretically  the order of magnitude of parameters is also in the order of tens of millions. It is difficult for online services to support this level of data volume, which requires engineering improvement on the sparsity of the model. It is important to focus on the key features and discard secondary features. Even if it may impact some certain model prediction accuracy, it will help reduce online inferencing latency and reduce the consumption of engineering resources.
- (2)  What are the key technical points to enhance the model's sparsity? We can add L1 regularization term or adopt a training method with strong sparsity such as FTRL.
- (3)  There are many technical approaches to achieving the goal. When it is impossible to determine which technology is better, it is a good choice to implement all of them, and use offline and online indicators for comparison.
- (4)  Determine the final technical approach based on the data and improve the engineering implementation.

This is the simplification method on the model side. Of course, the same idea can be adopted in the online feature reduction. Firstly, the method of principal component analysis can be used for feature screening. Then, the online features can be reduced without significantly impacting the model performance. For the features that are not easy to choose, conduct offline evaluation and online A/B testing to finally reach the level that the engineering system can support.

