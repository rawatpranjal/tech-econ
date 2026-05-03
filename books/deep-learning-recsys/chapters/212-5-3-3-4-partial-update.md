## 5.3.3.4 Partial Update

Another  idea  to  improve  a  model's  real-time  performance  is  to  perform  a  partial update. The general idea is to reduce the update frequency of the part with low training

efficiency and increase the update frequency of the part with high training efficiency. The representative of this approach is the 'GBDT+LR' model from Facebook.

Section 2.6 has introduced the model structure of 'GBDT+LR.' The model uses GBDT for automatic feature engineering, and uses LR to fit the optimization target. GBDT is serial and needs to train each tree sequentially, so the training efficiency is low and the update cycle is long. If the entire model of 'GBDT+LR' is trained every time, the inefficiency of GBDT will slow down the update of LR speed. In order to utilize the feature processing capability of GBDT and the ability of LR to quickly fit the optimization target, the deployment method adopted by Facebook is to train the GBDT model once a day. After the GBDT model is fixed, the LR model is trained in real-time to quickly capture the overall changes in the data. Through a partial update of the model, the balance between GBDT and LR capabilities is achieved.

The method of 'partial update of the model' is mostly used in the deep learning model with an embedding layer and neural network. Since the parameters of the embedding layer takes up most of the parameters of the deep learning model, its training process will slow down the overall convergence speed of the model. Therefore, in real application, it often adopts a mixed strategy: pre-training the embedding layer and frequently updating the model above the embedding layer. This is another application of the 'partial update.'

