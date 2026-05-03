## 2.7.3 Viewing LS-PLM from the Perspective of Deep Learning

In 2012, when LS-PLM models were just put into production, deep learning was still far from being a successful application in the field of recommender systems. But  if  we  look  at  it  today  and  revisit  LS-PLM  models  from  the  perspective  of deep learning, it would seem that LS-PLM models already had a strong sense of deep learning.

The next section explains the LS-PLM model with concepts of deep learning. It can be read as a warm-up for the deep learning sections that follow.

LS-PLM can be viewed as a three-layer neural network model with some attention mechanism. The input layer is the feature vector of the sample, and the middle layer is a hidden layer composed of m neurons, where m is the number of partitions. For a CTR estimation problem, the last layer of LS-PLM is naturally an output layer composed of a single neuron.

So where is the attention mechanism applied? In fact, between the hidden layer and the output layer, the weights between neurons are determined by the attention score obtained by the partitioning function. That is, the probability of a sample belonging to a partition is equivalent to its attention score.

Of course, this revisit of LS-PLM models from the perspective of deep learning is more about the model structure. In terms of implementation details, it is still different from a typical deep learning model nowadays. But undeniably, LS-PLM has approached the door of deep learning in its own way as early as 2012.

