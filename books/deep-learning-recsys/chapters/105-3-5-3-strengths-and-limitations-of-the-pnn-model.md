## 3.5.3 Strengths and Limitations of the PNN Model

The highlight of the PNN model is that it emphasizes the versatility of interaction methods between feature embedding vectors. Compared with the simple, undifferentiated processing in the fully connected layer, the inner product and outer product operations adopted by the PNN model obviously focus more on the interaction between different features, which makes it easier for the model to capture the interacting relationship of the features.

However, the PNN model also has some limitations. For example, in the practical application of the outer product operation, a lot of simplification operations have to be performed to optimize the training efficiency. Furthermore, performing an indiscriminate crossover of all features, to some extent, ignores the valuable information contained  in  the  original  feature  vector.  It  then  comes  down  to  questions  such  as how to integrate original features and crossed features to make feature crossing more efficient.  The  Wide&amp;Deep model and various deep learning models based on FM introduced in the later sections will give their solutions.

