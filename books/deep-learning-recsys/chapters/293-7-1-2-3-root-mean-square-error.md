## 7.1.2.3 Root Mean Square Error

Root mean square error (RMSE) is often used to measure the quality of the regression model. When using the click-through rate prediction model to build a recommender system, the recommender system actually predicts the probability of a positive sample. It can be evaluated by RMSE, which is defined as follows,

<!-- formula-not-decoded -->

where y i is the ground truth label of i -th sample,  ˆ y i is the predicted value of the i -th sample, and n is the number of samples.

In general, RMSE can well reflect the degree of deviation between the predicted value of the regression model and the true value. However, in practical applications, if there are individual outliers with a very large degree of deviation, the RMSE can become quite large even if the number of outliers is small. To solve this problem, mean  absolute  percent  error  (MAPE)  is  often  adopted  to  improve  the  robustness against outliers. The definition of MAPE is as follows,

<!-- formula-not-decoded -->

Compared with RMSE, MAPE is equivalent to normalizing the error of each sample, which reduces the impact of absolute error brought by individual outliers.

