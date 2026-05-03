## 8.3.5 Ranking Model

Using  the  candidate  generation  model,  hundreds  of  candidate  videos  are  generated, and then the ranking model is used for precise ranking. The ranking model of YouTube's recommender system is shown in Figure 5.8.

At first glance, readers may think that the network structure of the ranking model is not much different from that of the candidate set generation model. Indeed, this is the case in terms of model structure. Here, we need to focus on the input layer and output layer of the model, that is, the feature engineering and optimization objectives of the ranking model.

Compared with the candidate generation model, which needs to screen millions of candidate sets, the ranking model only needs to sort hundreds of candidate videos, so more features can be introduced for precise ranking. Specifically, the features from left to right in the input layer are:

- (1)  The embedding of the current candidate video (impression video ID embedding).
- (2)  The average embedding of the last N videos watched by the user (watched video IDs average embedding).
- (3)  The embedding of the user's language and the embedding of the current candidate video's language (language embedding).
- (4)  The time interval since the user last watched a video on the same channel (time since last watch).
- (5)  The  number  of  times  the  video  has  been  exposed  to  the  user  (#previous impressions).

Among these  five  features,  the  meanings  of  the  first  three  are  intuitive.  Here  we will focus on the fourth and fifth features, as these two features effectively capture YouTube's observations of user behavior.

The fourth feature, 'time since last watch' represents the interval time between the user watching videos of the same type. From the user's perspective, if a user has

just watched a video from the 'Classic DOTA Game Review' channel, the user is likely to continue watching videos from this channel. This feature captures this user behavior very well.

The fifth feature '#previous impressions' introduces the 'exploration and exploitation' mechanism described in Section 5.7 to avoid continuous ineffective exposure of the same video to the same user and increase the possibility of the user seeing new videos.

It should be noted that the ranking model not only introduces the original feature values for the fourth and fifth features, but also performs square and square root operations. As a new feature input to the model, this operation introduces nonlinearity of the features and improves the model's ability to express the features.

After passing through a three-layer ReLU network, the ranking model uses a different output layer from that of the candidate generation model. The candidate generation model chooses softmax as its output layer, while the ranking model chooses weighted logistic regression as the model output layer. At the same time, the output layer function chosen during the model serving phase is e Wx b ( ) + . Why does YouTube choose different output layer functions for training and serving phases?

Starting from YouTube's business model, increasing user watch time is the main optimization goal of its recommender system. Therefore, when training the ranking model, the expected watch time per impression should be a more reasonable optimization objective. Therefore, in order to directly predict the watch time, YouTube uses the watch time of positive samples as the sample weight and trains with weighted logistic regression, which enables the model to learn the information of actual watch time.

Assuming the probability of an event happening is p , a new concept called 'odds' is introduced here, which refers to the ratio of the event happening to not happening. For logistic regression, the probability p of an event happening is obtained from the sigmoid function, as shown,

<!-- formula-not-decoded -->

Here, the variable Odds is defined as shown in Equation 8.10 and by substituting it into Equation 8.9, we get,

<!-- formula-not-decoded -->

It is obvious that YouTube uses the variable Odds as the output of the model in the model serving. Why does YouTube predict the variable Odds? What is the physical meaning of Odds?

Further explanation is needed based on the principle of weighted logistic regression. Since weighted logistic regression introduces the information of positive sample weights, in the YouTube scenario, the viewing time T i of positive sample i is its sample weight. Therefore, the probability of a positive sample occurrence becomes T i times the original probability, and the Odds of positive sample i becomes,

<!-- formula-not-decoded -->

In the video recommendation scenario, the probability p of a user opening a video is often a very small value (usually around 1%), so Equation 8.11 can be further simplified:

<!-- formula-not-decoded -->

It can be seen that the physical meaning of the variable Odds is the expected viewing time for each impression, which is exactly the optimization target that the ranking model hopes to achieve. Therefore, using weighted logistic regression for model training and e Wx b ( ) + for model service is the most suitable technical implementation for optimizing this target.

