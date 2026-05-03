## 7.1.1.1 Holdout Test

The holdout test is a basic offline evaluation method, which randomly divides the original sample set into two parts - the training set and the testing set. For example, for a recommendation model, the samples can be randomly divided into two parts according to the ratio of 70%:30%, where 70% of the samples are used for model training and 30% of the samples are used for model evaluation.

The disadvantage of the holdout test is obvious. The evaluation metric calculated on the testing set is directly related to the division of the training set and the testing set. If only a small amount of holdout test is performed, the conclusions obtained will be relatively random. In order to eliminate this randomness, the idea of cross-validation is proposed.

