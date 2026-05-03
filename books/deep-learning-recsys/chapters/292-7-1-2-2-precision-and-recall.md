## 7.1.2.2 Precision and Recall

Precision is the ratio of the number of correctly classified positive samples against the number of predicted positive samples, while recall is the ratio of the number of correctly classified positive samples to the number of true positive samples.

In the ranking model, there is usually no definite threshold to directly judge the prediction result as a positive sample or a negative sample. The precision rate (Precision@N) and recall rate (Recall@N) of the Top N-ranked results are usually used to evaluate the ranking model's performance. In this case, the Top N items are considered the positive samples predicted by the model in the precision rate and recall rate calculation.

Precision rate and recall rate are contradictory indicators. In order to improve the precision rate, the model needs to predict the sample as a positive sample when it has high confidence, but it often misses many true positive samples when the model is not so confident, which results in a lower recall rate.

In order to comprehensively reflect the results of precision and recall, the F1-score is  often  adopted.  F1-score  is  the  harmonic  mean  of  precision  and  recall,  which  is defined as follows:

<!-- formula-not-decoded -->

