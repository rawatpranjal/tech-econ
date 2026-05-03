## 8.1 Deep Learning Recommender Systems by Facebook

In  2014,  Facebook  (currently  Meta,  the  following  uses  Facebook  as  the  company name, since the paper was published in 2014) published a paper on their advertising recommender system, Practical Lessons from Predicting Clicks on Ads at Facebook [1], which proposed the classic GBDT+LR CTR model structure. Strictly speaking, the  GBDT+LR model structure does not belong to the category of deep learning. However, at that time, this work opened up a new stage of feature engineering modeling and automation using the GBDT model for automatic feature combination and selection. Since then, deep learning techniques such as Deep Crossing and Embedding have  been  applied  to  feature  engineering  and  gradually  transitioned  to  full  deep

learning networks. In a sense, Facebook's advertising recommender system based on GBDT+LR became a bridge connecting the era of traditional machine learning recommender systems and the era of deep learning recommender systems. In addition, its online learning, online data integration, downsampling on negative samples, and other technologies adopted as early as 2014 still have strong engineering significance today.

In  2019,  Facebook  released  their  latest  deep  learning  model,  DLRM  (Deep Learning Recommender Model) [2], which uses a classic deep learning model architecture and is trained on a CPU+GPU platform. It is an innovative attempt at a deep learning recommender system in the industry.

This section will first introduce Facebook's implementation of the recommender system based on the GBDT+LR combination model and then delve into the model details and implementation of DLRM.

