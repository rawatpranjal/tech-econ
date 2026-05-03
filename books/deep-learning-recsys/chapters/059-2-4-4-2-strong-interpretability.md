## 2.4.4.2 Strong Interpretability

Intuitively, the mathematical expression of an LR model is the weighted sum of features, transformed by a sigmoid function. Supported by its mathematical definition, the simple expression of LR is also very consistent with human intuition about the estimation process.

The weighted sum of each feature is used to synthesize the impact of different features on CTR. Because different features are not equally important, the weights are assigned to features to represent their importance. Finally, using the sigmoid function to map the values into a probability ranging between 0 and 1, which is exactly consistent with the meaning of CTR.

The  immediate  intuition  of  LR  clearly  has  other  benefits  -  making  the  model extremely interpretable. The importance of features can be easily explained by the value of the weights. It is also quite straightforward to locate which factors affect the final result when the prediction is off. This will make it easy to give explainable reasons when cooperating with colleagues in operations and products, effectively reducing communication costs.

