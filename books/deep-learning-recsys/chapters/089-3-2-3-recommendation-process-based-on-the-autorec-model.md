## 3.2.3 Recommendation Process Based on the AutoRec Model

The recommendation process based on the AutoRec model is not complicated. Given the rating vector of the input item i is r i /g11 /g12 , the output vector of the model h ( ; ) r i /g11 /g12 /g84 is

the prediction of ratings for the item i by all users. Then, ˆ R ui represents the rating prediction of user u for item i , as shown in Eq. 3.4.

<!-- formula-not-decoded -->

By traversing the input item vector, the rating predictions of all items from user u can be obtained. Then the recommendation list can be generated based on the rating predictions.

Like the collaborative filtering algorithm introduced in Section 2.2, AutoRec is also divided into item-based AutoRec and user-based AutoRec. The input vector in the formula introduced here is the rating vector of the item, so it can be called I-AutoRec (Item-based AutoRec). If the user's rating vector is used as the input vector, then we will  get  U-AutoRec  (User-based  AutoRec). In the process of recommendation list generation, the advantage of U-AutoRec over I-AutoRec is that it only needs to input the user vector of the target user once, and then the user's rating vector for all items can be constructed. That is to say, only one model inference process is needed to obtain the user's recommendation list; the disadvantage is that the sparsity of the user vector may affect the model's effectiveness.

