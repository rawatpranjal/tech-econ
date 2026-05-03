## 2.3.4 Advantages and Limitations of Matrix Factorization

Compared with CF, matrix factorization obviously has a few advantages:

- (1)  Strong generalization ability. It partially solved the problem of sparse data.
- (2)  Low space complexity. Instead of storing the 'huge' user similarity or item similarity matrix required in the CF model, just store the user and item latent vectors. The space complexity is reduced from n 2 to ( ) n m k /g14 /g152 .
- (3)  Better scalability and flexibility. The final output of matrix factorization is the latent vectors for users and items, which is actually congruous with the idea of embedding in deep learning. Therefore, the result of matrix factorization can also be easily combined and spliced with other features, which enables it to combine with deep learning networks seamlessly.

Meanwhile, matrix factorization also has its limitations. Like CF, it is also inconvenient to add users, items, and context-related features, which makes it ineffective in utilizing additional information, and unable to make effective recommendations when lacking  the  user's  historical  behavior  data.  In  order  to  solve  this  problem,  the  LR model and its subsequently developed models such as FMs have gradually become more widely used in the field of recommender systems because of their natural ability to integrate these features.

