## 2.3.3 Eliminating the Scoring Bias

Different users have different scoring systems (for example, on a scale of 1 through 5 with 5 being the best, some users think that a score of 3 is very low, while some users think that a score of only 1 is poor evaluation). The measurement standards

for  different  items  are  also  different  (for  example,  the  average  score  of  electronic products and the average score of daily necessities may be quite different). In order to eliminate the scoring bias for users and items, a common practice is to add bias vectors to users and items in the matrix factorization, as shown in Equation 2.10:

<!-- formula-not-decoded -->

where µ is the global bias constant, b i is the item bias coefficient, which can be the mean of all ratings received for item i, and b u is the user bias coefficient, which can be the mean of all ratings given by user u.

In the meantime, the objective function for matrix factorization also needs to be changed from Equation 2.8 to 2.11.

<!-- formula-not-decoded -->

Similarly, matrix factorization needs to be solved differently with the change of the objective function. The main difference is that a new gradient descent formula needs to be calculated by differentiating the new objective function. The details will not be repeated here.

After adding the scoring bias for users and items, the latent vectors obtained by matrix factorization can better reflect the 'true' attitude distinctions of different users toward different items, and it is easier to capture valuable information in the evaluation data, thereby avoiding biased recommendation results.

