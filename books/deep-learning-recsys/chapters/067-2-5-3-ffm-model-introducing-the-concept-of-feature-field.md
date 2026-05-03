## 2.5.3 FFM Model: Introducing the Concept of Feature Field

In  2015,  the  Field-aware  Factorization  Machines  (FFM)  model  [6]  developed from FM won the top prizes in several CTR prediction competitions. It was then

adopted  by  many  companies  such  as  Criteo  and  Meituan  in  their  recommender systems.  Compared  to  FM  models,  the  FFM  model  introduced  the  concept  of field-awareness, which makes the model more expressive.

<!-- formula-not-decoded -->

Equation 2.22 shows the second-order part in the mathematical expression of FFM. The difference between FFM and FM is that the latent vector has changed from the original w j 1 to w j f 1 2 , , which means that each feature no longer corresponds to a single latent vector, but instead to a set of latent vectors. When feature x j 1 is interacted with feature x j 2 , x j 1 will  interact  with  the  latent  vector w j f 1 2 , from x j 2 's  corresponding feature field f 2 . Similarly, x j 2 will also interact with the latent vector from x j 1 's corresponding feature field f 1 .

What does the field mean here? Simply put, 'field' represents the feature field, and the features in the field are generally a one-hot feature vector formed by one-hot encoding. For example, the gender of the user is usually divided into three categories: male, female, and unknown. For a female user, the feature vector from one-hot encoding is [0, 1, 0], and this three-dimensional feature vector is a 'gender' feature field. Connecting all feature fields forms the overall feature space of the sample.

Next,  an  example  from  the  Criteo  FFM  paper  [6]  is  presented  to  illustrate  the characteristics of FFM in details. Suppose the training samples received during the recommendation model training process are as shown in Figure 2.11. Here, Publisher, Advertiser, and Gender are the three feature fields, and ESPN, NIKE, and Male are the feature values of these three feature fields (one-hot encoding is still needed).

If it were in FM, the features ESPN, NIKE, and Male would have corresponding latent vectors w w w ESPN NIKE Male , , . Then the weights for interacted feature pairs ESPN and NIKE, ESPN and Male would be w w ESPN NIKE ⋅ and w w ESPN Male ⋅ . Among them, the latent vector w ESPN  is invariant in the two feature interactions.

On the other hand, in FFM, the weights of interacted feature pairs ESPN and NIKE, ESPN and Male are w w ESPN A NIKE P , , ⋅ and w w ESPN G Male P , , ⋅ , respectively.

You may have noticed that ESPN uses different latent vectors w ESPN A , and w ESPN G , , respectively, when interacting with NIKE and Male. This is because NIKE and Male are in different feature fields Advertiser (A) and Gender (G).

In the training process of FFM models, there are f feature fields with n features in each field, and each feature is represented by a k -dimensional latent vector. Hence, there are n k f ⋅ ⋅ features that need to be learned with the model. In terms of training, the quadratic terms of FFM are not as simplified as in FM, and its complexity is kn 2 .

Figure 2.11 Example training sample.

Ф(w, x) =

• 0

Ф(w, x) =

WESPN,NIKE

WESPN

+

+

Compared to FM, FFM's introduction of the concept of feature field includes more valuable information to the model and makes the model more expressive. But at the same time, the computational complexity of FFM increases to kn 2 ,  which is much larger than the kn of FM. In the practical engineering applications, it is necessary to make a trade-off between model effect and engineering cost.

