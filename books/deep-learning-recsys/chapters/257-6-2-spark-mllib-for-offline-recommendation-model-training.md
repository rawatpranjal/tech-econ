## 6.2 Spark MLlib for Offline Recommendation Model Training

We would  like  to  make  an  analogy  between  recommender  systems  and  cooking. Whether a chef can make a good dish depends on three key points:

- (1)  Qualities of the cooking ingredients, like whether they are sufficient and fresh.
- (2)  Cooking skills of the chef.
- (3)  Performance while cooking. Whether the chef can make the best use of the materials and how well the chef can perform while cooking.

Correspondingly, the data collected in recommender systems are the 'cooking ingredients,' and the richness and freshness of data are equivalent to the 'sufficiency' and 'freshness' of these ingredients. The offline training model of the recommender system corresponds to the chef's training process. The more the chef is trained, the more types of cooking materials he has tried, the better his cooking skills could be. The online serving of recommendation systems can be analogized to the process of the chef 'presenting his cooking skills.' A good dish cooked by the chef on-site doesn't not only require all the ingredients to have consistently high quality as usual, but also requires high standards during the cooking process and making suitable adjustments based on the customer's taste.

Next,  we  will  introduce  how  the  recommender  system  trains  its  'cooking skills' in an offline environment, and how to keep 'high performance' on-site, so that the online service can provide real-time recommendations that best suit the user's 'taste.'

In  internet  applications  such  as  recommendation,  advertising,  and  search,  the massive data volume in the size of terabyte or even petabyte-level makes it almost impossible  to  complete  the  model  training  in  a  single-machine  environment. Distributed  machine  learning  training  provides  a  solution.  With  respect  to  the offline  model  training,  we  will  introduce  three  mainstream  solutions  for  distributed machine learning training, respectively - Spark MLlib, Parameter Server, and TensorFlow. They are not the only frameworks to choose from, but also represent three  main  approaches  in  distributed  training.  In  this  section,  we  will  start  with Spark MLlib and describe how it handles the problem of parallel training as the most popular big data framework.

Although challenged by rising stars such as Flink, Spark is still the most popular  computing  framework  in  the  industry.  Many  companies  choose  Spark's  native machine learning framework, MLlib, for model training to maintain consistency with the technology stack adopted in the data and model pipeline. Spark MLlib became the first choice for distributed training in machine learning, not only because Spark is widely adopted, but also because Spark MLlib's parallel training approach represents a naive and intuitive solution.

