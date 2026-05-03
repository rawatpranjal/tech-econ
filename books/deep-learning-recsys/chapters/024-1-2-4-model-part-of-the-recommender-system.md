## 1.2.4 Model Part of the Recommender System

The 'model part' is the main body of the recommender system (as shown in light blue in Figure 1.4). The structure of the model is generally composed of the 'Retrieval Layer,' 'Ranking Layer' and 'Re-ranking Layer.'

-  The 'Retrieval Layer' generally uses efficient rules, algorithms or simple models  to  quickly  retrieve  items  that  users  may  be  interested  in  from  a  massive candidate set.
-  The 'Ranking Layer' uses the sorting model to fine-sort the candidate sets that are initially screened.
-  The 'Re-ranking Layer' can combine some supplementary methods and algorithms to make certain adjustments to the recommendation list, so that additional factors such  as  'diversity,'  'popularity,'  and  'freshness'  of  the  results  are  taken  into account, before finally forming a user-visible recommendation list.

This  process,  from  the  recommendation  model  receiving  the  set  of  all  candidate items, to finally generating the recommendation list, is generally referred to as the model-serving process.

Before  performing  model  services  in  an  online  environment,  model  training  is required  to  determine  the  model  structure,  the  parameter  weights  in  the  structure, and the parameters in related algorithms and strategies. According to the different training  environments of the model, the training methods can be divided into two parts: 'offline training' and 'online updating.' The advantage of offline training is that it can utilize the entire set of samples and features to make the model approach the global optimum; while online updating focuses on 'digesting' new data samples in quasi-real-time and reflecting new data trends more quickly to meet the real-time requirements of the model.

In addition, to evaluate the recommendation model and facilitate iterative optimization, the model part of the recommender system provides various evaluation modules such as 'offline evaluation' and 'online A/B testing.' These offline and online evaluation indicators are used to guide the next iterative model optimization.

All of these modules together constitute the technical framework of the model part of the recommender system. The model part, particularly the 'Ranking Layer' model, is its focus, and it is also the focus of research in the industry and academia. Therefore, the following chapters focus on the model part, especially the mainstream technology of the 'Ranking Layer' models and their evolution trends.

