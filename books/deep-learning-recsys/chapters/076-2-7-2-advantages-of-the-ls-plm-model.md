## 2.7.2 Advantages of the LS-PLM Model

The  LS-PLM  model  is  suitable  for  industrial-level  recommendation,  advertising, and  other  large-scale  sparse  data  scenarios,  mainly  because  of  the  following  two advantages:

- (1) End-to-end nonlinear learning ability: LS-PLM has the ability to partition the training sample. Thus, it can mine the nonlinear patterns contained in the data and save a lot of manual data processing and feature engineering. As a result, the LS-PLM algorithm can make the training end-to-end, which facilitates the unified modeling of different applications and business scenarios with a global model.
- (2) Strong model sparsity: LS-PLM incorporates L1 and L2 norm regularization during modeling, which gives the final fitted model higher sparsity and lightweight deployment. In model online service, it only needs to use features with nonzero weights, so the sparse model also makes it more efficient for online inference.

