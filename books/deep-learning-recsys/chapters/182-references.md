## References

- [1]  Tomas  Mikolov,  et  al.  Distributed  representations  of  words  and  phrases  and  their compositionality. Advances in Neural Information Processing Systems , 26, 2013.
- [2]  Tomas Mikolov, et al. Efficient estimation of word representations in vector space: arXiv preprint arXiv:1301.3781 (2013).
- [3]  Xin  Rong.  Word2vec  parameter  learning  explained:  arXiv  preprint  arXiv:1411.2738 (2014).
- [4]  Yoav Goldberg, Omer Levy. Word2vec explained: Deriving Mikolov et al.'s negative-sampling word-embedding method: arXiv preprint arXiv: 1402.3722 (2014).
- [5]  Yoshua Bengio, et al. A neural probabilistic language model. Journal of Machine Learning Research , 3, 2003: 1137-1155.
- [6]  Oren  Barkan,  Noam  Koenigstein.  Item2vec:  Neural  item  embedding  for  collaborative  filtering.  2016  IEEE  26th  International  Workshop  on  Machine Learning for Signal Processing (MLSP), Salerno, Italy, September 13-16, 2016.
- [7]  Bryan  Perozzi,  Rami  Al-Rfou,  Steven  Skiena.  DeepWalk:  Online  learning  of  social representations.  Proceedings  of  the  20th  ACM  SIGKDD  International  Conference  on Knowledge Discovery and Data Mining, New York, USA, August 24-27, 2014.
- [8]  Aditya  Grover,  Jure  Leskovec.  node2vec:  Scalable  feature  learning  for  networks. Proceedings  of  the  22nd  ACM  SIGKDD  International  Conference  on  Knowledge Discovery and Data Mining, San Francisco, USA, August 13-17, 2016.

- [9]  Jizhe Wang, et al. Billion-scale commodity embedding for e-commerce recommender in  Alibaba.  Proceedings  of  the  24th  ACM  SIGKDD  International  Conference  on Knowledge Discovery and Data Mining, London, UK, August 19-23, 2018.
- [10]  Jian Tang, et al. Line: Large-scale information network embedding. Proceedings of the 24th  International  Conference  on  World  Wide  Web.  International  World  Wide  Web Conferences Steering Committee, Florence, Italy, May 18-22, 2015.
- [11]  Daixin Wang, Peng Cui, Wenwu Zhu. Structural deep network embedding. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, San Francisco, USA, August 13-17, 2016.
- [12]  Malcolm Slaney, Michael Casey. Locality-sensitive hashing for finding nearest neighbors [lecture notes]. IEEE Signal Processing Magazine , 25(2), 2008: 128-131.

While building a recommender system, a good recommendation model is important, but only having a good model is not enough. In fact, recommender systems need to solve complex problems, and all technical details are essential to the final recommendation performance. This requires machine learning engineers to examine the system from multiple perspectives, not only to grasp the core of the model, but also to think about the recommender system holistically.

This  chapter  will  dive  deeper  into  recommender  systems  from  seven  different angles. We hope to present a comprehensive walkthrough for the relevant knowledge in recommender systems. The contents include:

- (1)  How do recommender systems select and process features?
- (2)  What are the popular strategies of the retrieval layer in recommender systems?
- (3)  Why is it important to have real-time recommender systems? How to improve the real-time performance of the model?
- (4)  How to choose the best optimization objective for the recommendation model based on specific scenarios?
- (5)  How to improve model structure based on user intent?
- (6)  How to solve the cold start problem in recommender systems?
- (7)  What  is  the  'exploration  vs.  exploitation'  problem?  What  are  the  common solutions?

There is no logical relationship among these problems, but they are all essential components of recommender systems besides the recommendation model. Only by understanding these problems can we build a recommender system with comprehensive capabilities and robust architecture.

