## 5.6.1 Rules-Based Cold Start Process

During  the  cold  start  process,  due  to  the  lack  of  data,  the  engine  for  personalized recommendation cannot work effectively. Naturally, the system can be rolled back to the 'pre-recommender system' era and adopt a rule-based recommendation method. For example, in a user cold start scenario, lists such as 'hot charts,' 'recent  trends,'  and  'highest  ratings'  can  be  used  as  the  default  recommendation lists. In fact, most music, video and other applications use this method as the default rule for cold start.

Furthermore, you can refer to domain expert opinions to create some personalized item lists, and make coarse-grained rule-based recommendations based on the limited information of users, such as age, gender, and addresses inferred from IP when registering. For example, use the click-through rate or other similar targets to build a decision tree of user attributes, build a cold start list at the leaf node of each decision tree, and after the new user completes registration, find the corresponding leaf node on the decision tree and use this list to complete the user cold start process.

In the item cold start scenario, other similar items can be found according to some rules, and the cold start process of the item can be completed by using the recommendation logic of similar items. Of course, finding similar items is a strongly business-related task. This section uses Airbnb as an example to illustrate the process.

Airbnb is the world's largest short-term rental platform. When launching a new short-term rental house, Airbnb will designate a 'cluster' for the rental house according to its properties, and houses in the same 'cluster' will have similar recommendation rules. So the following three rules are relied upon by the designate 'cluster' for cold start short-term rental housing:

- (1)  Same price range.
- (2)  Similar housing attributes (area, number of rooms, and so on).
- (3)  The distance to the target house is within 10 kilometers.

To complete cold start for a new short-term rental house in the market, find three similar houses that best meet these rules, and locate the cluster based on the clusters of these three existing houses.

From this example, we can see that the rule-based cold start method is more relied on the business insights from domain experts. When formulating cold start rules,  it  is  necessary  to  fully  understand  the  company's  business  characteristics and make full use of existing data in order to make cold start rules reasonable and efficient.

