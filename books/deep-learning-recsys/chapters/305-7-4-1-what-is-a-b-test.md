## 7.4.1 What Is A/B Test?

A/B test, also known as split test or bucket test, is a random experiment. It usually divided the test group into control (A) and treatment (B). By varying a single variable, it  compares the performance of the control and treatment groups correspondingly, and then draws the experiment conclusions based on the collected performance metrics. Specific to the models used in the internet applications, users can be randomly divided into control and treatment groups. Then, the new model is applied to the users in the treatment group, and the old model is applied to the users in the control group.

With some data collection and analysis, the experimenter can get comparisons on the selected online metrics.

Compared with offline evaluation, there are three main reasons why online A/B testing cannot be skipped:

-  Offline evaluation cannot completely eliminate the impact of data bias.
-  Offline evaluation cannot fully reproduce the online condition. Generally speaking, offline evaluation often does not consider the data latency, data loss, label missing, and so on. Therefore, the offline evaluation results often have some deviation from the reality.
-  Some business metrics of the online system cannot be calculated in the offline evaluation. Offline evaluation generally evaluates the model itself, and cannot directly obtain other metrics related to the business target. Taking the new recommendation model as an example, offline evaluation often focuses on improving the ROC curve and PR curve, while online evaluation can fully understand the changes in user click rate, retention time, PV visits, and so on. These metrics can be only obtained through online A/B testing.

