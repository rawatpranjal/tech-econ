## 7.1.2.1 Accuracy

Classification accuracy refers to the ratio of correctly classified samples against the total number of samples, that is,

<!-- formula-not-decoded -->

where n correct is the number of correctly classified samples and n total is the total sample count.

Accuracy is a relatively intuitive evaluation metric in classification tasks. Although it  has  strong  interpretability,  it  also  has  drawbacks.  When  the  proportion  of  samples in different categories is very imbalanced, the category with a large proportion often becomes a factor that affects the accuracy rate. For example, if negative samples account for 99%, then the classifier can predict all samples as negative samples to obtain 99% accuracy.

For a click-through rate prediction classification problem, the recommendation model can be evaluated with the accuracy rate under the premise of selecting a threshold to determine positive and negative samples. In the actual recommendation scenario, the more common use case is to generate a recommendation list. So the combination of precision and recall are more commonly used to measure the performance of recommendations.

