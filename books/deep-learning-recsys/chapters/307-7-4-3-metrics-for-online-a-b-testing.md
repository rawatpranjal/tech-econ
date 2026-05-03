## 7.4.3 Metrics for Online A/B Testing

Generally speaking, the A/B testing is the last test before the model goes online. The model that passes the A/B test will directly serve the online users to meet the company's business goals. Therefore, the metrics of A/B testing should be consistent with the business key performance indicator (KPI).

Table 7.4 Main evaluation metrics for online A/B testing in various recommender systems

| Recommender System Category   | Online A/B Metrics                                                                                                                                                                           |
|-------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| E-commerce News               | Click-through rate, conversion rate and unit customer spending Retention rate (number of users who are still active after x of total users before x days), average session duration, average |
|                               | days/number number of clicks                                                                                                                                                                 |
| Video                         | Play completion rate (play time/video time), average play time, total play time                                                                                                              |

Table 7.4 lists the main evaluation metrics for online A/B testing of e-commerce, news and video recommendation models.

Readers should have noticed that the metrics of online A/B testing are quite different from those of offline evaluation (such as AUC, F1-score, and so on). Offline evaluation does not have the conditions to directly calculate the business KPIs, so the next best  thing  is  to  choose  model-related  metrics  just  for  technical  evaluation  purposes. However, at the company level, there is more interest in the business KPIs that can drive business growth. Therefore, when an online testing environment is available, it is necessary to use A/B testing to verify the effect of the model on improving business KPI. In this case, the role of online A/B testing can never be replaced by offline evaluation.

