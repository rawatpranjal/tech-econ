## 3.5.2 Multiple Feature Intersection Forms in the Product Layer

The main innovation of the PNN model for the deep learning structure is the   introduction of  the  product  layer.  Specifically,  the  product  layer  of  the  PNN  model  consists  of a linear operation part (block z of the product layer in Figure 3.12) and a product operation part (block p of the product layer in Figure 3.12). Among them, the product feature interaction part can be divided into inner product type and outer   product type. The PNN model using inner product operation is called Inner   Product-based Neural Network (IPNN), and the PNN model using outer product operation is called Outer Product-based Neural Network (OPNN).

Whether it is an inner product type or an outer product type, it is a form of pairwise combination of different feature embedding vectors. In order to ensure the smooth operation of the product, the dimensions of each embedding vector must be the same.

The inner product is a classic vector manipulation method. Assuming that the input feature vectors are f i and f j respectively, the inner product equation g i j inner ( ) , f f can be defined as,

<!-- formula-not-decoded -->

The outer product operation is to cross each dimension of the input feature vectors f i and f j for each pair of elements to generate a feature cross matrix. The outer product equation g i j outer ( ) , f f can be defined as,

<!-- formula-not-decoded -->

The outer product operation generates a square matrix with the dimension of M M × , where M is the dimension of the input vector. It is clear that such an operation will directly increase the complexity of the algorithm from the order of M originally to M 2 . In order to reduce the burden of model training, a dimensionality reduction method was introduced in the PNN model paper. The results of the outer product of the feature embedding vectors are super-positioned to form a combined outer product matrix p , as shown,

<!-- formula-not-decoded -->

From the final form of Equation 3.7, the final superposition matrix p is  similar  to applying an average pooling on all the feature embeddings and then performing the outer product operation.

In practical applications, the operation of average pooling should also be treated with caution. Because the corresponding dimensions of different features are averaged, it is actually assumed that the corresponding dimensions of different features have similar physical meanings. But obviously, if one feature is 'age' and the other

is 'region,' then after these two features have passed through their respective embedding layers, the embedding vectors of the two are not in the same vector space, which is obviously not comparable. At this time, averaging the two will obscure a lot of valuable information. The average pooling often occurs in the embeddings in the same domain; for example, the embedding of multiple items browsed by the user is averaged. Therefore, the outer pooling operation of the PNN model needs to be cautious, and carefully balanced between training efficiency and model performance.

In  fact,  after  the  linear  and  product  operations  of  the  features,  the  PNN  model does not directly send the results to the upper L 1 fully connected layer (as shown in Figure 3.12), but performs a local fully connected layer conversion inside the product layer. It maps the linear portion z ,  the product portion p into D 1 -dimensional input vectors l z and l p respectively. D 1 is the number of hidden units in the L 1 hidden layer. The mapped vectors l z and l p are superimposed and passed into the hidden layer. This part of the operation is commonly seen and can be replaced by other types of transformation operations, so it will not be described in detail here.

