## 7.1.2.4 Logarithmic Loss Function

Logarithmic loss function (LogLoss) is another metric that is often used in offline evaluation. In a binary classification problem, LogLoss can be defined as follows,

<!-- formula-not-decoded -->

Among them, y i is  the  ground  truth  label  of  the  sample x i , P i is  the  probability  of predicting that the input sample x i is a positive sample, and N is the total number of samples.

Readers could find that LogLoss is the loss function of logistic regression. A large number of deep learning models use logistic regression (that is, Sigmoid) or Softmax as the output layer. Therefore, using LogLoss as an evaluation metric can very intuitively reflect the change of the model's loss function. From the perspective of the model, LogLoss is a very suitable evaluation metric for the model's convergence.

