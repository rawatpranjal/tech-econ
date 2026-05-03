## 8.1.7 Parallel Training Method in the DLRM Model

As a paper from the industry, the actual training methods of the DLRM model can often benefit peers in the industry. Due to the huge amount of data at Facebook, the single-node model training cannot support the model training task in time. Therefore, model parallel training is a necessary solution.

In short, the DLRM model uses a combination of model parallelism and data parallelism, adopting model parallelism for the embedding part and data parallelism for the MLP part. The purpose of using model parallelism for the embedding part is to

Accuracy

0.79-

0.78-

0.77

0.761

0.75

0

0.5

0.795 -

0.790

0.785

alleviate  the  memory bottleneck problem caused by a large number of embedding layer parameters. Data parallelism is used for the MLP and interaction layers to parallelize forward and backward propagation. · DLRM DCN

Model parallel training of the embedding layer means that only a portion of the embedding layer parameters are saved on one device or computing node, and each device only updates the embedding layer parameters on its own node during parallel mini-batch gradient updates. (b) Adagrad

Data parallel training of the MLP and interaction layers means that each device already has all the model parameters, and each device calculates gradients using part of the data, and then uses the AllReduce method to summarize all the gradients for parameter updates.

