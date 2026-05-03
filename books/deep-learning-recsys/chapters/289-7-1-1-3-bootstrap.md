## 7.1.1.3 Bootstrap

Both the holdout test and the cross-validation are based on the method of dividing whole datasets into training and testing sets. However, when the sample size is relatively  small,  sample  set  division  will  further  reduce  the  training  sample  amount, which may affect the training effect of the model. Is there an evaluation method that can maintain the sample size of the training set? The bootstrap approach can solve this problem to a certain extent.

Bootstrap is a test method based on the resampling technique. For a sample set with size of n , random sampling with replacement is performed n times to obtain a training set with size of n . In the n -time sampling process, some samples will be re-sampled, and some samples will not be drawn. The bootstrap method uses these undrawn samples as a testing set for model evaluation.

