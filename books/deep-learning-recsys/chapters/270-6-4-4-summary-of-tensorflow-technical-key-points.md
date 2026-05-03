## 6.4.4 Summary of TensorFlow Technical Key Points

This  section  presents  the  operation  of  the  deep  learning  platform  represented  by TensorFlow from the perspective of the training mechanism. The technical key points can be summarized as follows:

- (1)  The principle of TensorFlow is to convert the model training process into a task relationship graph. The training data flows in the task relationship graph in the form of tensors to complete the entire training.
- (2)  TensorFlow performs task scheduling and parallel computing based on the task relationship graph.
- (3)  For distributed training in TensorFlow, its training process can be divided into two layers. One layer is the data-parallel training process based on the Parameter Server architecture, and the other layer is the parallel computing process at the CPU+GPU task level inside each worker node.

Learning TensorFlow and its tuning will involve a lot of basic knowledge. The models, operations, and training methods supported by TensorFlow are also very comprehensive. We don't intend to give a very in-depth introduction. Interested readers can use the contents of this chapter as a starting point, and use the official documents and tutorials provided by TensorFlow as a guide for more systematic learning.

