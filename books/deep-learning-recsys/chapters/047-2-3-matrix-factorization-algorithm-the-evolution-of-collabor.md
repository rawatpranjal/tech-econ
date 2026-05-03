## 2.3 Matrix Factorization Algorithm: The Evolution of Collaborative Filtering

Section 2.2 introduced one of the most classic models in the field of recommender systems - CF. To address the CF algorithm's pronounced Matthew effect and weak generalization ability, a matrix factorization (MF) algorithm is proposed. Based on the 'co-occurrence matrix' in the CF algorithm, MF incorporates the concept of a latent vector and strengthens the model's ability to deal with sparse matrices, which solves the main problems of CF.

In  2006,  Netflix  held  its  famous  competition  recommendation  algorithms,  the 'Netflix  Prize  Challenge,'  in  which  algorithms  based  on  MF  demonstrated  great potential and opened the prelude to the popularity of MF in the industry [3]. This section uses an example of the Netflix recommendation application to illustrate the principle of the MF algorithm.

