## 2.4 Logistic Regression: A Recommendation Model That Combines Multiple Features

While  CF  models  make  recommendations  only  based  on  user-item  interactions, LR models can collectively utilize various features from users, items, and contexts to  generate  more  'comprehensive'  recommendation  results.  In  addition,  another form of LR, 'perceptron,' as the most basic single neuron in the neural network, is the basic structure of deep learning. Therefore, LR models capable of multifeature fusion have become another major direction of development for recommendation models other than CF.

Compared with CF and matrix factorization, which use the 'similarity' of users and items for recommendation, LR treats the recommendation problem as a classification problem, and ranks items by the predicted probability of positive feedback. The positive feedback here can be the user 'clicking' on a certain product, or the user 'watching' a certain video. Therefore, LR transforms the recommendation problem into a Click Through Rate (CTR) estimation problem.

