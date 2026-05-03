## 3.4.3 Strengths and Limitations of NeuralCF Models

The NeuralCF model actually proposes a model framework - it is based on the two embedding layers of the user vector and the item vector, uses different interaction layers to cross the features, and can flexibly concatenate different interaction layers. From this, we can see the advantages of deep learning in building a recommendation model - using the ability of neural networks to fit arbitrary functions in theory, flexibly combining different features, and increasing/decreasing the complexity of the model as needed.

In practice, it should be noted that it is not always true that the more complex the model structure and the more features, the better. We need to understand the consequence induced by adding more complexities to the model: (1) risk of overfitting; (2) demand of a larger amount of training data; and (3) longer training time. These aforementioned aspects are what algorithm engineers need to consider while making tradeoff decisions between model practicability, real-time performance, and effectiveness.

The NeuralCF model also has its own limitations. Since it is developed on the basis of collaborative filtering, the NeuralCF model does not introduce other types of features, which undoubtedly wastes other valuable information in practical applications. In addition, there is no further exploration and categorization of feature interaction types in the model. It requires deeper dives in the follow-up research.

