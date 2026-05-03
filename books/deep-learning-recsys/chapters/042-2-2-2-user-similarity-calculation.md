## 2.2.2 User Similarity Calculation

In  the  process  of  CF,  the  calculation  of  user  similarity  is  the  most  critical  step. According to the introduction in Section 2.2.1, the rows in the co-occurrence matrix represent users. Then, the problem of calculating the similarity between user i and user j is to calculate the similarity between user vector i and user vector j . A few similarity calculation methods that are commonly used are as follows:

- (1)  Cosine similarity, as shown in Equation 2.1. Cosine similarity measures the vector  angle  between  user  vector i and  user  vector j .  Obviously,  the  smaller  the included angle is, the greater the cosine similarity is, and the more similar the two users are.

<!-- formula-not-decoded -->

- (2)  Pearson correlation coefficient, as shown in Equation 2.2. Compared with cosine similarity, the Pearson correlation coefficient reduces the impact of user rating bias by using the user average score to correct each independent rating.

<!-- formula-not-decoded -->

where R i p , represents the rating of item p by user i. R i represents the average rating of all items by user i, and P represents the set of all items.

- (3)  Based on the idea of the Pearson coefficient, the influence of item scoring bias on the results can also be reduced by introducing the average item score, as shown in Equation 2.3.

<!-- formula-not-decoded -->

where R p represents the average of all ratings for item p.

In the calculation of user similarity, in theory, any reasonable 'vector similarity definition' can be used. While improving traditional CF, researchers also solve some of the shortcomings by improving the definition of similarity.

