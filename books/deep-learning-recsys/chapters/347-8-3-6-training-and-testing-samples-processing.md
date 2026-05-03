## 8.3.6 Training and Testing Samples Processing

To improve the model's training efficiency and accuracy, YouTube has implemented various engineering measures to process training samples, including the following three experiences for readers to reference:

- (1)  The candidate generation model transforms the recommendation problem into a multiclassification problem. In the scenario of predicting the next viewing, each candidate video is a category, so there are millions of categories in total. Using softmax for training is undoubtedly inefficient. How did YouTube solve this problem? YouTube adopted  the  negative  sampling  training  method  commonly  used  in  Word2vec  to reduce the number of classifications predicted each time and accelerate the convergence speed of the entire model. The specific method has been introduced in Section 4.1.  In  addition,  YouTube  also  tried  another  commonly  used  training  method  in Word2vec, hierarchical softmax, but did not achieve good results. Therefore, the more convenient negative sampling method was chosen in practice.
- (2)  In the preprocessing of the training set, YouTube did not use the raw user logs, but extracted an equal number of training samples for each user. Why did they do this? The purpose of this approach is to reduce the excessive influence of highly active  users  on  the  model  loss,  preventing  the  model  from  becoming  biased toward the behavioral patterns of active users and ignore the experience of more numerous long-tail users.
- (3)  Why does YouTube use the user's most recent viewing behavior as the test set instead of using the classic random holdout method for the test set? Using only the  last  viewing  behavior  as  the  test  set  is  mainly  to  avoid  introducing  future information in the model training process.

YouTube's training and testing processes are based on the observation and understanding of business data, which is a very good engineering practice to follow.

