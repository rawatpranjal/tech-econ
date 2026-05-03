## 7.2.3 Mean Average Precision

Mean average precision (mAP) is another commonly used evaluation metric in recommender systems and information retrieval. This metric is actually an average of

.30

.1

Average Precision (AP). Before calculating mAP, readers need to understand what average precision is.

Assume that the ranking results of a user test set by the recommender system are shown in Table 7.2, where 1 represents the positive sample, and 0 represents the negative sample.

In the previous section, we introduced how to calculate precision@N. Then what is the precision@N at each position of this ranking list? The results are shown in Table 7.3.

The calculation of AP only takes the precision for different topN for average calculation, that is, AP ( / / / / ) / . /g32 /g14 /g14 /g14 /g32 1 1 2 4 3 5 4 6 4 0 6917. How about mAP?

If the recommender system sorts the samples of each user in the test set, then we can get an AP value for each user. The average AP value of all users is then the mAP value.

It is worth noting that the calculation method of mAP is completely different from the calculation methods of the P-R curve and the ROC curve, because mAP needs to sort the samples for each user, while both P-R curve and ROC curve can be calculated with the sorted full test set. This difference needs special attention in the actual calculations.

