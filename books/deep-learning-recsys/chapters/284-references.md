## References

- [1]  Fay  Chang,  et  al.  Bigtable:  A  distributed  storage  system  for  structured  data. ACM transactions on Computer Systems (TOCS) , 26.2 (2008): 4.
- [2]  Sanjay Ghemawat, Howard Gobioff, Shun-Tak Leung. The Google file system. 2003.
- [3]  Jeffrey Dean, Sanjay Ghemawat. MapReduce: Simplified data processing on large clusters. Communications of the ACM , 51.1, 2008: 107-113.
- [4]  Mu Li, et al. Scaling distributed machine learning with the parameter server. 11th USENIX Symposium on Operating Systems Design and Implementation (OSDI 14), Broomfield, CO, USA, October 6-8, 2014.
- [5]  Mu  Li,  et  al.  Parameter  server  for  distributed  machine  learning. Big  Learning  NIPS Workshop , 6(2), 2013.
- [6]  Martín Abadi, et al. TensorFlow: Large-scale machine learning on heterogeneous distributed systems: arXiv preprint arXiv: 1603.04467 (2016).
- [7]  Martín Abadi, et al. TensorFlow: A system for large-scale machine learning. 12th USENIX Symposium on Operating Systems Design and  Implementation  (OSDI  16),  Savannah, GA, USA, November 2-4, 2016.

The proportion of knowledge related to the evaluation of the recommender system is not large in the entire recommender systems knowledge framework, but its importance  is  as  significant  as  building  a  recommender  system.  The  evaluation  mainly includes the following three points:

- (1)  The metrics used in the evaluation of the recommender systems directly determine whether the optimization of the recommendation system is objective and reasonable.
- (2)  The evaluation is a collaborative effort, which requires the machine learning team to communicate and cooperate with other teams.
- (3)  The selected metrics directly determine whether the recommender system meets the company's business goals and development vision.

These three points are the keys to the success of a recommender system.

This chapter focuses on the evaluation of recommender systems, from offline evaluation to online experiment. It discusses the methods and metrics of recommendation system evaluation from multiple levels, including the following:

- (1)  Offline evaluation methods and metrics.
- (2)  Offline simulation evaluation - replay.
- (3)  Online A/B testing and online metrics.
- (4)  Fast online evaluation method - interleaving.

These evaluation methods are not independent. At the end of this chapter, we will discuss how to combine different levels of evaluation methods to form a scientific and efficient multilayer recommender system evaluation architecture.

