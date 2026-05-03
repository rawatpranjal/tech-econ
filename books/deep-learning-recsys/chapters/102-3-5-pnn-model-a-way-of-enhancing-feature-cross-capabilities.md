## 3.5 PNN Model: A Way of Enhancing Feature Cross Capabilities

The main idea of the NeuralCF model introduced in Section 3.4 is to use a multilayer neural network to replace the dot product operation of classical collaborative filtering to  enhance the expressiveness of the model. In a broader sense, any manipulation

CTR

Hidden Layer 2

Fully Connected

Hidden Layer 1

Fully Connected

Product Layer

12

method between vectors can be used to replace the inner product operation of collaborative filtering, and the corresponding model can be called a generalized matrix factorization model. However, the NeuralCF model only mentions two fields of feature vectors, the user vector and the item vector. How to design the feature crossing method if multiple sets of feature vectors are added? In 2016, the PNN (Productbased Neural Networks) model proposed by researchers from Shanghai Jiao Tong University [5] gave several design ideas for feature interaction.

