## 5.6 Solutions to Cold Start

Cold start is a problem that recommender systems must face. Any recommender system has to start from scratch, with very few data and features, and gradually grow into rich dataset. So with the lack of valuable data, how to make effective recommendations is the problem of 'cold start.'

Specifically, the cold start problem is mainly divided into three categories based on how data is lacking:

- (1)  User cold start: After a new user signs up, how can personalized recommendations be made without historical behavior data?

- (2)  Item cold start: After a new item (new movie, new product, and so on) is added, how can the item be recommended to users without an interaction record for the item?
- (3)  System  cold  start:  When  the  recommender  system  lacks  all  relevant  historical data at the beginning of its operation.

For different application scenarios, solving the cold start problem requires business insight, and a reasonable strategy based on the opinions of domain experts. Generally speaking,  the  mainstream  cold  start  strategies  can  be  classified  into  the  following three categories:

- (1)  Rule-based cold start process;
- (2)  Enrich available features;
- (3)  Utilize  active  learning,  transfer  learning,  and  'exploration  vs.  exploitation' mechanisms.

