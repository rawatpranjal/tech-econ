## 5.3.3.5 Real-Time Update of the Client Model

Earlier in this section, we mentioned the real-time methods of 'features' on the client. Since the client is the part closest to users and has the best real-time capability, can we update the model on the client based on the newly generated user behavior?

Real-time client model update is still in the exploratory stage in the recommender system industry. For some computer vision problems, lightweight models can be generated through model compression and deployed on the client, but for 'heavyweight' models like recommendation models, it is often dependent on the server where relatively powerful computing resources and rich feature data are available. Nonetheless, the client can often save and update some parameters and features of the model, such as the current user's embedding vector.

The logic and motivation here is that in the deep learning recommender system, the model often needs to take two critical feature vectors: user embedding and item embedding. For the update of item embedding, global data is generally required, so it can only be updated on the server; for user embedding, however, it relies more on the user's own data. Therefore, moving the user embedding update to the client, which can reflect the user's latest behavior to the user embedding, so that the recommendation results can be updated in real-time on the client.

Here is a simple example to illustrate the process. If the user embedding is obtained by averaging the item embeddings clicked by the user, then the client, as the first to obtain the latest item information clicked by the user, can update the user embedding in real-time based on these items, and save the embedding. When making the next recommendation, the updated user embedding is sent to the server, and the server can return real-time recommendation content according to the latest user embedding.

