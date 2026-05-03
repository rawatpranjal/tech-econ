## 6.3.4 Summary of Technical Key Points in Parameter Server

The key points of Parameter Server in distributed machine learning model training are as follows:

-  Replace the synchronized blocking gradient descent strategy with an asynchronized non-blocking distributed gradient descent strategy.
-  Implement  a  multiserver  node  architecture  to  avoid  bandwidth  bottlenecks  and memory bottlenecks caused by a single-server node.

-  Utilize engineering methods such as consistent hashing, parameter range pulling, and parameter range pushing to achieve minimal data transfer. This design avoids  global  network  congestion  and  bandwidth  waste  caused  by  broadcast operations.

Parameter Server is only a framework to manage the parallel training and does not involve specific model implementation. Therefore, Parameter Server is often used as a component of MXNet and TensorFlow. To implement a machine learning model specifically, it is necessary to rely on general and comprehensive machine learning frameworks.  Section  6.4  introduces  the  mechanism  of  modern  machine  learning frameworks represented by TensorFlow.

