## 7.2.4 Selecting Reasonable Evaluation Metrics

In addition to three commonly used metrics like P-R curve, ROC curve, and mAP, there are many other metrics used in the recommender system evaluation, such as Normalized Discounted Cumulative Gain (NDCG), coverage, and diversity, and so on. In the actual offline experiment, although it is necessary to evaluate the model from different angles, there is no need to pursue perfection to find the 'best' metric. Choosing too many metrics to evaluate the model could sometimes result in a waste of  time.  The  purpose  of  offline  evaluation  is  to  quickly  detect  the  issues,  eliminate  unreliable  candidates,  and  find  promising  candidates  for  online  evaluation. Therefore, selecting two to four representative offline metrics based on the business scenarios and conducting efficient offline experiments is the correct path for offline evaluation.

Table 7.2 Example of ranking results

| Ranking List       | N = 1 N =   | 2 N = 3   | N = 4   |   N = 5 N |   = 6 |
|--------------------|-------------|-----------|---------|-----------|-------|
| Ground Truth Label | 1 0         |           | 0 1     |         1 |     1 |

Table 7.3 Examples of precision@N calculation

| Ranking List       | N = 1   | N = 2   | N = 3   | N = 4   | N = 5   | N = 6   |
|--------------------|---------|---------|---------|---------|---------|---------|
| Ground Truth Label | 1       | 0       | 0       | 1       | 1       | 1       |
| Precision@N        | 1/1     | 1/2     | 1/3     | 2/4     | 3/5     | 4/6     |

