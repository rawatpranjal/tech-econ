## 8.3.1 Application Scenarios

As the world's largest video-sharing website, almost all videos on the YouTube platform are from user-generated content (UGC). This content has two common characteristics:

- (1)  Unlike Netflix or some other major video streaming services, which mainly purchase or produce top content, YouTube's content is very diverse. This makes its business mode quite different from the other streaming services. The main effect of YouTube's content is not as obvious as those of streaming providers.
- (2)  Due to the vast number of videos on YouTube, it is difficult for users to discover content they like.

These characteristics of YouTube's content make the recommender system more critical than other streaming services. In addition, YouTube's main source of profit comes from video advertising, and the exposure opportunities of advertisements are directly proportional to the user's viewing time. Therefore, the YouTube recommender system is the foundation of its business model.

Based on YouTube's business model and content characteristics, its recommendation team built two deep learning networks that consider recall and precision requirements, respectively. They also constructed a ranking model with user watch time as the  optimization goal to maximize user watch time and generate more advertising exposure  opportunities.  The  following  describes  in  detail  the  model  structure  and technical specifics of the YouTube recommender system.

