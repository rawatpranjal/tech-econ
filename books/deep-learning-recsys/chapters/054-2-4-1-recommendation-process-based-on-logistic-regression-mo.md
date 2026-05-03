## 2.4.1 Recommendation Process Based on Logistic Regression Models

The recommendation process based on LR is as follows:

- (1)  Convert features such as user's age, gender, item attributes, item description, current time, and current location into numeric vectors.
- (2)  Determine  the  optimization  goal  of  the  LR  model  (taking  optimization  of  the 'click-through  rate'  as  an  example),  use  the  existing  sample  data  to  train  the model, and determine the parameters.
- (3)  In the model service stage, the features are input into the model, then through the inference of the LR, the probability of an item being 'clicked' by a user (here, click is used as the positive feedback) is obtained.
- (4)  Use the probability of 'clicking' to sort all candidate items to obtain the recommendation list.

The focus of this recommendation process is to use the features of the sample data for model training and online inference. The next sections will discuss the mathematical expression, inference process, and training methods of LR models.

