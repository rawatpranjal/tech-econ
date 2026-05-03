## 2.3.2 Solving Matrix Factorization

There are three main methods to solve for MF: Eigenvalue Decomposition, Singular Value  Decomposition  (SVD),  and  Gradient  Descent.  Among  them,  Eigenvalue Decomposition can only be applied on square matrices, which makes it unsuitable for decomposing user-item matrices.

Here is a description of SVD:

Assuming  an m × n -dimensional  matrix M .  There  must  be  a  decomposition M U V /g32 /g54 T , where U is an m × m orthogonal matrix, V is an n × n orthogonal matrix, and Σ is an m × n diagonal matrix.

Take the largest k elements in the diagonal matrix Σ as the latent factors, delete the other dimensions of Σ and the corresponding dimensions in U and V , and the matrix M is decomposed into M U V /g124 /g117 /g117 /g117 m k k k k n /g54 T . This is the MF with k -dimensional latent factors.

As it described earlier, SVD seems to solve the problem of MF perfectly. However, it has two defects, which make it yet unsuitable as the main method of MF in internet applications:

- (1)  SVD requires the original co-occurrence matrix to be dense. But in the internet application, most users have very little historical behavior data, which leads to a very sparse co-occurrence matrix. This is contrary to the application conditions of SVD. If SVD is applied, the missing elements must be filled in.
- (2)  The computational complexity of traditional SVD is as high as O ( mn 2 ) [4], which is almost unacceptable for internet applications with millions of products and tens of millions of users.

For  the  earlier  two  reasons,  traditional  SVD  is  also  unsuitable  for  solving MF  problems  with  large-scale  sparse  matrices.  Therefore,  the  gradient  descent method has become the main practice for MF, which is described in detail further.

Equation 2.7 is the objective function for solving MF with gradient descent. The purpose of this function is to minimize the difference between the original score r ui  and the product of the user vector and the item vector q p i T u , so as to preserve maximum information of the original co-occurrence matrix.

<!-- formula-not-decoded -->

where K is the set of all user ratings. In order to reduce the overfitting problem, the objective function after adding the regularization term is shown in Equation 2.8.

<!-- formula-not-decoded -->

