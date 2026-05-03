## 2.2.3 Sorting of the Final Results

After obtaining top n similar users, the process of using top n users to generate the final  recommendation  results  is  as  follows.  Assuming  that  'the  preferences  of  the target user and its similar users are similar,' the preference of the target user can be predicted according to the existing evaluations of similar users. The most commonly used method here is to obtain the preference prediction of the target user by using the user similarity and the weighted average of the evaluations of similar users, as shown in Equation 2.4.

<!-- formula-not-decoded -->

where the weight w u,s is the similarity between user u and user s, and R s,p is the rating of user s to item p.

After obtaining user u's preference predictions for different items, the final recommendation list can be obtained by sorting according to the prediction scores. So far, the entire recommendation process of CF is completed.

The algorithm introduced earlier makes recommendations based on user similarity; therefore, it is also called user-based collaborative filtering (UserCF). Intuitively, it  makes  sense  because  'items  liked  by  friends  with  similar  interests  will  be  my preference as well.' However, from a technical point of view, it also has some shortcomings, mainly including the following two points:

- (1)  In an internet application scenario, the number of users is often much larger than the number of items, and UserCF needs to maintain a user similarity matrix to quickly find top n similar users. The storage overhead of the user similarity matrix is very large, and with the development of the business, the increase of users will cause the requirement for storage to grow rapidly at the speed of n 2 , which is an unbearable expansion of the online storage system.

- (2)  The user's historical data is often very sparse. For users with only a few purchases or click behaviors, the accuracy of finding similar users is very low, which makes UserCF unsuitable for applications that are difficult  to  obtain  positive feedback for (such as hotel reservations, bulky commodity purchases, and other low-frequency applications).

