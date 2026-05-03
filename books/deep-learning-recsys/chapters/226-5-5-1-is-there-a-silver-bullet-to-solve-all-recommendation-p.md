## 5.5.1 Is There a 'Silver Bullet' to Solve All Recommendation Problems?

While communicating with peers in the recommendation industry, one question is often asked: 'Which recommendation model is better?' It is true that model structure is critical to the final recommendation performance, but is there really a model structure that is the 'silver bullet' to solve all recommendation problems?

To answer this question, we can start with analyzing a model - the recommendation model DIEN proposed by Alibaba in 2019. The details of DIEN model were introduced in Section 3.9, and we will briefly review in this section. The overall structure of the DIEN model is a GRU sequence model, and it simulates the evolution of user interests through the sequence model. The interest evolution part first converts item ID to item embedding based on the user behavior sequence from the behavior layer. The interest extraction layer uses the GRU sequence model to simulate the user interest evolution and extracts the interest embedding vector. The interest evolution layer combines the attention mechanism with the AUGRU sequence model to simulate the interest evolution process associated with targeted advertising.

Since the model was proposed, due to Alibaba's huge influence in the industry, many practitioners believe that they have found a 'silver bullet' to solve the recommendation problem. However, many problems emerge from the actual application,

and people tend to look into the model itself for solutions to these problems. For example, 'Is the dimension of the embedding layer not enough?' 'Is it necessary to increase the number of states in the interest evolution layer?' and so on.

The point is, anyone who raised such questions defaulted to a premise, that is, the  DIEN  model  that  can  improve  the  performance  in  Alibaba's  recommendation scenarios should be equally effective in other application scenarios. However, is this assumption really reasonable? Is the DIEN model the 'silver bullet' in the field of recommender systems?

The answer is no.

Let's make a simple analysis. Since the key of DIEN is to simulate and express the evolution of user interest, the premise of model application must be that there is 'interest evolution' in the use case. Alibaba's use case is very easy to understand - users' buying interests change at different times. For example, after purchasing a laptop, a user will have a certain probability of purchasing its peripheral products; after purchasing a certain type of clothing, a user may choose some other clothing that matches it. These are intuitive examples of interest evolution.

Another reason why DIEN can be effective in Alibaba's use case is that the user's interest evolution path can be nearly completely preserved in the data flow. As China's largest e-commerce group, Alibaba's product matrix composed of various product lines can almost completely capture the migration of user shopping interest. Of course, users may go shopping on other e-commerce platforms, thus interrupting the evolution of shopping interest in Alibaba. However, statistically speaking, the interest evolution of a large number of users can still be captured by Alibaba's data system.

Therefore, the prerequisite for the DIEN model is that the use case needs to meet two conditions:

- (1)  There is an 'interest evolution' in application scenarios and
- (2)  The evolution process of user interests can be completely captured by the data.

If either one of the two conditions is not established, then the DIEN model will probably not bring great benefits.

Take the video streaming media recommender system as an example. On a comprehensive streaming media platform (such as a smart TV), users can choose their own channels and content, or choose to watch Netflix, YouTube, or other streaming media channels. Once the user enters Netflix or another third-party application, we cannot get the specific data in the application. In this case, the system can only obtain part of the user's viewing and clicking data. It is not easy to extract the user's points of interest; much less can we talk about building the entire evolution path of the user's interest. Even if the interest evolution path is barely constructed, it is an incomplete or even wrong path.

Based on such characteristics, is DIEN suitable to be the main architecture of the recommendation model? The answer is no. The DIEN model cannot reflect the characteristics of business data and user motivations. In this situation, it would be unwise to think that the poor model performance is due to the parameters not properly adjusted or sample size not large enough. Compared with these technical reasons, it is most important to understand the use case and be familiar with the data characteristics.

At this point, we are ready to give the answer to the question in the title - while building a recommendation model, it is most important to start from the application scenario and follow the characteristics of user behavior and data, and propose a reasonable motivation to improve the model.

In other words, the model structure is not the 'silver bullet' for building a good recommender system. The real 'silver bullet' is good observations of user behavior and application scenarios. Based on these observations, improve the model structure to best express these characteristics. The following three examples are further illustrations of this statement.

