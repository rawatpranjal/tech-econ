## 6 Engineering Implementations in Deep Learning Recommender Systems

In  previous  chapters,  we  introduced  the  key  technical  points  of  deep  learning recommender systems from multiple perspectives, mainly from the theoretical and algorithm aspects. However, algorithms and models are only 'good wine'; after all, they must be served in a suitable 'container' to present the best taste. The 'container' here refers to the engineering platform that implements the recommender systems.

From an engineering perspective, recommender systems can be divided into two parts - data and model. The data part mainly covers the related engineering implementations of the data pipeline needed by recommender systems, while the model part  refers  to  the  development  of  the  recommendation  model.  Furthermore,  the model development can be further divided into offline training and online serving based on the different stages of model application. Following the overall engineering architecture of recommender systems, this chapter is presented in three parts:

- (1)  Data pipeline of recommender systems. We will introduce the main framework of the big data platform associated with data pipeline in a recommender system and the mainstream technologies for implementing the big data platform.
- (2)  Offline training of deep learning recommendation models. It mainly introduces the popular platforms for training deep learning recommendation models, such as Spark MLlib, Parameter Server (parameter server), TensorFlow, and PyTorch.
- (3)  Online deployment of deep learning recommendation models. We will cover the technical approaches to deploying deep learning recommendation models and the process of model online serving.

In addition to the engineering frameworks, we will also discuss the trade-off between engineering implementation and theory. Then we will share some of our thoughts on how algorithm engineers should make trade-offs balance between practice and theory.

