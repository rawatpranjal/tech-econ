## 2.5.1 POLY2 Model: The Beginning of Feature Interaction

For feature interaction, machine learning engineers often combine features manually and then filter the features through various analysis methods. But this method is  undoubtedly  inefficient.  Unfortunately,  human  experience  is  often  limited,  and engineers usually do not have the time and energy to find the optimal combination of features. Therefore, a 'brute force' combination of features using the POLY2 model becomes a viable option.

The mathematical expression of the POLY2 model is shown in Equation 2.20:

<!-- formula-not-decoded -->

As you can see, the model interacts with all features pairwise (features x j 1 and x j 2 ) and assigns weights wh j j ( , ) 1 2 to all feature interactions. POLY2 solves the problem to a certain extent by interacting features with brute force. The POLY2 model is still a linear model in nature, and its training method is not different from LR, so it is convenient for engineering compatibility.

But the POLY2 model has two major flaws:

- (1)  While processing internet data, one-hot encoding is often used to process categorical data, resulting in extremely sparse feature vectors. And POLY2 performs nonselective  feature  interaction,  which  makes  the  feature  vectors  even  more sparse. As a result, the learning of the weights for most of the interaction vectors cannot converge due to the lack of valid data.
- (2)  The number of parameters is increased from n to n 2 , which greatly increases the training complexity.

