## 5.1.3.1 Continuous Features

Typical examples of continuous features are the aforementioned numerical features such as user age, statistical features, item release time, and video playback duration. For the processing of such features, the most commonly used methods include normalization, discretization, and adding nonlinear functions.

The main purpose of normalization is to unify the dimensions of each feature and normalize continuous features to the [0,1] interval. You can also do 0-mean normalization,  that  is,  normalize  the  original  dataset  to  a  dataset  with  a  mean  of  0  and  a variance of 1.

Discretization is the process of dividing the original continuous values into buckets by determining the quantiles, and finally forming discrete values. The main purpose of discretization is to prevent overfitting caused by continuous values and uneven distribution of values. The discretized continuous features are converted into feature vectors for the recommendation model, just like the one-hot encoded categorical features.

Adding a nonlinear function is to directly transform the original feature through a  nonlinear  function,  and  then  add  both  the  original  feature  and  the  transformed feature  to  the  model  for  training.  Commonly  used  nonlinear  functions  include

<!-- formula-not-decoded -->

The purpose of adding a nonlinear function is to better capture the nonlinear relationship between the feature and the optimization objective, and enhance the nonlinear expressivity of this model.

