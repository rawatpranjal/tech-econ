## 1.2.3 Data Part of the Recommender System

The data part of the recommender system (as shown in beige in Figure 1.4) is mainly responsible for the information collection and processing of 'users,' 'items,' and 'context.'  Specifically,  the  three  platforms  responsible  for  data  collection  and processing  are  ranked  according  to  the  ability  of  real-time  performance,  namely 'client-side and server-side real-time data processing,' 'quasi-real-time data processing on stream processing platform,' and 'offline data processing on big data platform.' While the real-time performances decrease, the massive data processing capabilities of the platforms increase. Therefore, the data flow framework of a mature recommender system will use the three platforms to complement each other and utilize them together.

After obtaining the original data information, the data processing system will further process the original data. There are three main data exports after processing:

- (1)  Generate the sample dataset required by the recommendation model for training and evaluation.
- (2)  Generate the 'features' required for the recommendation model serving for online inference of the recommender system.
- (3)  Generate statistical data required for system monitoring and business intelligence (BI) systems.

To some extent, the data part of the recommender system is the 'water source' of the entire system. Only by ensuring the continuity and purity of the 'water source' can the recommender system be continuously 'nurtured' to operate efficiently and output accurately.

