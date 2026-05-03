## 6.3 Parameter Server for Offline Recommendation Model Training

In Section 6.2, we gave a detailed introduction to the parallel training method in Spark MLlib. Spark adopts a simple and direct data-parallel method to solve the problem of model parallel training. But Spark's parallel gradient descent method is using synchronized blocking approach, and the model parameters need to be transferred to all nodes through global broadcasting. These processes make Spark's parallel gradient descent calculation relatively inefficient.

In order to solve this problem, the Parameter Server [4,5], a distributed and scalable framework, was proposed in 2014. It almost perfectly solves the distributed training problem of machine learning models. Today, Parameter Server is not only directly adopted in the machine learning platforms of some big companies, but also integrated into mainstream deep learning frameworks such as TensorFlow and MXNet, as an important solution for distributed training of machine learning.

