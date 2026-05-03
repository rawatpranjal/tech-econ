## 8.3.3 Candidate Generation Model

First, we introduce the architecture of the candidate generation model (as shown in Figure 8.9). Looking at this network from the bottom up, the input of the bottom layer is the user's historical video embedding vector and search query embedding vector.

..•

gender

To  generate  video  embedding  and  search  query  embedding,  YouTube  uses  a method similar to the Airbnb embedding method introduced in Section 8.2. It uses the Word2vec method to embed videos and search queries based on the user's viewing and search sequences, and then uses them as inputs to the candidate generation model. The specific method can refer to the process of Airbnb embedding for house listings in Section 8.2. In addition to pre-embedding, an embedding layer can also be directly added to the deep learning network for end-to-end training with the upper MLP layers. The pros and cons of these two methods have been discussed in Section 4.5.

Apart from the video and search term embedding vectors, the feature vectors also include the user's geographic feature embedding, age, gender, and so on. All the features are then concatenated and input into a ReLU neural network for training.

After three layers of neural networks, the softmax function is used as the output layer. YouTube sees the problem of selecting a candidate video set as a next-watch recommendation problem for users. The final output of the model is a probability distribution over all candidate videos. Clearly, this is a multiclassification problem, which is why softmax is used as the final output layer.

Overall, the candidate generation model of the YouTube recommender system is a standard deep neural network model that uses pre-trained embedding features.

