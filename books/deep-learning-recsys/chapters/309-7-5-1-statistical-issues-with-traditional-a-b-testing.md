## 7.5.1 Statistical Issues with Traditional A/B Testing

In addition to efficiency limitations, traditional A/B testing also encounters certain issues  with  statistical  significance.  Let's  illustrate  this  with  a  classic  A/B  testing example.

Imagine designing an A/B test to assess whether there's a taste preference for Coca-Cola over Pepsi among users. In a traditional setup,  participants  would  be randomly  divided  into  two  groups  for  a  blind  taste  test  (where  brand  labels  are hidden). Group A would be given only Coca-Cola, while Group B would only get Pepsi. Consumption over a set period would then indicate a preference for one brand over the other.

While generally effective, this test has potential flaws:

In the test population, consumption habits vary widely, from those who rarely drink soda to heavy daily consumers. Heavy soda drinkers make up a small portion of the sample but may contribute disproportionately to overall consumption. This imbalance could skew results if either group has slightly more heavy consumers, leading to a distorted conclusion.

This issue also arises in online applications like Netflix. A small number of highly active users account for a significant portion of total watch time. So, if more of these active users end up in Group A than in Group B (or vice versa), it can impact the A/B test outcome and obscure the true model performance.

How to address this issue? One solution is to avoid dividing the test population into separate groups. Instead, allow all participants to choose freely between Coca-Cola and Pepsi (while still ensuring the brands remain unlabeled but distinct). At the end of the test, we can calculate each participant's consumption ratio between Coca-Cola and Pepsi, then average these ratios to get an overall preference.

A/B Test

User Group A

Ranking

Algorithm A

Conversion

Interleaving Test

Advantages of this approach include:

- (1)  It eliminates imbalances in user characteristics between groups.
- (2)  By assigning equal weight to each participant, it minimizes the impact of heavy consumers on the results.

This approach, where all test options are presented simultaneously to participants and preferences are used to derive evaluation results, is known as the Interleaving method.

Streaming

All Evaluation

