## 7.3.1 Logical Loop for Model Evaluation

To answer this question, it is necessary to revisit the core of model evaluation - how to evaluate a model and determine whether it is a 'good' model? Figure 7.3 shows the logical relationship of each component in the model evaluation.

The key point of offline evaluation is to make the results of offline evaluation as close as possible to online ones. To achieve this goal, the offline evaluation process should simulate the online environment as much as possible. The online environment includes not only the online data environment, but also production settings such as model update frequency.

