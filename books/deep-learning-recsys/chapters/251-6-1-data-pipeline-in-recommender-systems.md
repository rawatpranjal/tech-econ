## 6.1 Data Pipeline in Recommender Systems

In this section, we will walk through the data processing pipeline for training and serving recommendation models. Since 2003, when Google successively published three foundational papers in the field of Big Table [1], Google File System [2], and Map Reduce [3], the recommendation system has also entered the big data era. With

Мар

Shuffle

Reduce

TB or even PB size of training data, the data pipeline of recommender systems must be closely integrated with the big data processing and storage infrastructure to complete efficient training and online inferencing.

The development of big data platforms has gone through various stages from batch processing to stream computing, and then to full integration. The continuous development of architectural patterns has brought a substantial improvement in the freshness and flexibility of data processing. Following the order of development, the big data platform mainly includes four architectural modes: batch processing, stream computing, Lambda, and Kappa.

