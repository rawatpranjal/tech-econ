## 3.10.2 Deep Reinforcement Learning Recommendation Models

The agent part is the core of the reinforcement learning framework. For the recommendation agent, the model is the 'brain' of the system. In the DRN framework, the role of the 'brain' is the Deep Q-Network, DQN for short, where Q is the abbreviation of 'Quality.' It means that by evaluating the quality of the action, the utility score of the action is calculated and used for decision-making.

User Features

The network structure  of  DQN  is  shown  in  Figure  3.27.  The  concepts  of  reinforcement learning - state vector and action vector - are applied in feature engineering. User features and context features are classified as state vectors, because they are action independent. User-news crossing features and news features are treated as action features since they are related to the action of recommending news.

User features and environmental features are fitted by the multilayer neural network on the left to generate a value score V ( ) s . The state vector and action vector are used to generate an advantage score A ( , ) s a .  Finally, the score from both parts are combined to obtain the final quality score Q ( , ) s a .

