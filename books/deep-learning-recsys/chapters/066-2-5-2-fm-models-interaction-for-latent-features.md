## 2.5.2 FM Models: Interaction for Latent Features

To address the shortcomings of POLY2 models, in 2010, Rendle proposed the Factorization Machines (FM) model [5].

Equation 2.21 is the second-order part of FM. Compared with POLY2, the main difference  is  that  the  single  weight  coefficient wh j j ( , ) 1 2 is  substituted  by  an  inner product of two vectors ( ) w w j j 1 2 ⋅ . Specifically, FM learns a latent weight vector for each feature. When interacting features, the inner product of the two features' latent weight vectors is used as the weight of the interacted feature.

<!-- formula-not-decoded -->

In essence, the practice of introducing latent vectors in FM is similar to the practice of  matrix  factorization  using  latent  vectors  to  represent  users  and  items.  In  other words,  FM  is  a  further  expansion  of  the  idea  of  using  latent  vectors  in  matrix factorization, from latent vectors of simple users and items to all features.

FM dramatically reduces the number of parameters from the order of n 2 for  the POLY2 model to nk ( k is the dimension of latent vectors, n k by introducing latent vectors for all features. While training FM models using gradient descent, the computational complexity can also be reduced to the order of nk , which greatly reduces the training overhead.

The introduction of latent vectors enables FM to better solve the problem of data sparsity.  For  example,  in  product  recommendations,  the  sample  has  two  features, namely channel and brand, and the feature combination of a training sample is (ESPN, Adidas). In POLY2, the model can only learn the weight corresponding to this combined feature when ESPN and Adidas appear in a training sample at the same time; in FM, however, ESPN's latent vector can also be updated by (ESPN, Gucci) samples, while Adidas' latent vectors can also be updated by (NBC, Adidas) samples, which greatly reduces the model's requirement for data sparsity. Even for a feature combination that has never appeared before, such as (NBC, Gucci), the model has the ability to calculate the weight of this feature combination based on its previously learned latent vectors for NBC and Gucci, respectively. This is something that POLY2 cannot achieve. Compared with POLY2, although FM loses the exact information of some feature combinations, the generalization ability is greatly improved.

In terms of engineering, FM can also be learned with gradient descent, making it real-time and flexible. Compared with the complex network structure of deep learning models, which makes it difficult to deploy and serve online, FM's easier-to-implement model structure makes the online inference process relatively simple, and it is easier to deploy and serve online. Therefore, FM became one of the mainstream recommendation models in the industry around 2012-2014.

