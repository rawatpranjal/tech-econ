## 3.12.3 Inspiration and Challenges of LLM Adaptation in Recommender Systems

The recent developments of LLMs have not only attracted the world's attention to the AI field, but also opened a new 'gate' for recommender systems. The LLMs' astonishing understanding and reasoning abilities give us a new angle on building recommender systems, and also add a new powerful tool to our toolbox. However, we also need to acknowledge the challenges that we are facing in the LLM world.

At the end of the survey [19], the authors summarized the challenges from three aspects: (1) efficiency, (2) effectiveness, and (3) ethics:

- (1) Efficiency: This  includes  both  training  and  inference  latency.  As  the  model becomes bigger, it requires more training data to train the model effectively. Both the larger model size and larger training data can significantly increase the training efficiency. Also, the increased model parameter amount makes it challenging to finish the inferencing task under the limited time constraints in the online service.
- (2) Effectiveness: Even though many researchers have demonstrated the powerfulness of the LLMs, still the LLM can have its own shortcomings and limitations. Two examples are limited context window size and ID feature understanding. From past studies, we can see LLMs show a reduction of understanding ability when the input texts are too long in the prompt. For the other limitation, since the ID features are not semantically meaningful, so it will be quite hard for the LLMs to understand and differentiate the IDs in the model input.
- (3) Ethics: This is a quite common topic in recommender systems. The practitioners in the recommendation field have been studying many approaches for removing bias from recommender systems. It has also been found that LLMs can present certain biases originating from the pre-training corpus and could potentially generate harmful or offensive content.

Luckily, numerous researchers and engineers have been working on each aspect of these challenges and to create solutions to solve them. The reader can refer to the references in the survey to get more details about those solutions, to inspire research and actual implementations.

