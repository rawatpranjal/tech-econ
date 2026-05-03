## 8.2.5 Airbnb's Real-Time Search Ranking Model and Its Feature Engineering

Earlier, we introduced Airbnb's method of computing embeddings for users' shortterm and long-term interests in listings. It is important to note that Airbnb does not directly rank search results based on embedding similarity, but instead generates different user-listing pair features based on embeddings, which are then input into the search ranking model to obtain the final ranking results.

So what features does Airbnb generate based on embeddings? And how do these features drive online personalized search results? Table 8.4 lists all the embedding-based features.

It  is  clear  that  the  last  feature,  UserTypeListingTypeSim,  refers  to  the  similarity between the user type and listing type. This feature similarity is calculated using the longterm interest embeddings of user types and listing types. In addition, all other features apply to short-term interest embeddings. For example, EmbClickSim refers to the similarity between a candidate listing and the listing that the user most recently clicked on.

A  careful  reader  may  have  a  question  -  where  does  the  'real-time'  aspect  of Airbnb's system come into play? In fact, the answer to this question can be found in  the  feature  design.  Among  these  embedding-related  features,  Airbnb  has  added

Table 8.4 List of embedding-based user and listing features

| Feature Names                                                                                                         | Feature Descriptions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|-----------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| EmbClickSim EmbSkipSim EmbLongClickSim EmbWishlistSim EmbInqSim EmbBookSim EmbLastLongClickSim UserTypeListingTypeSim | Similarity between candidate listings and user's clicked listings Similarity between candidate listings and user's skipped listings Similarity between candidate listings and user's long clicked listings Similarity between candidate listings and user's saved listings Similarity between candidate listings and user's inquired listings Similarity between candidate listings and user's booked listings Similarity between candidate listings and user's last long clicked listings Similarity between candidate listing type and user type |

Table 8.5 Airbnb evaluation of different feature importance

| Feature Name           |   Coverage (%) | Feature Importance Ranking   |
|------------------------|----------------|------------------------------|
| EmbClickSim            |          76.16 | 5/104                        |
| EmbSkipSim             |          78.64 | 8/104                        |
| EmbLongClickSim        |          51.05 | 20/104                       |
| EmbWishlistSim         |          36.5  | 47/104                       |
| EmbInqSim              |          20.61 | 12/104                       |
| EmbBookSim             |           8.06 | 46/104                       |
| EmbLastLongClickSim    |          48.28 | 11/104                       |
| UserTypeListingTypeSim |          86.11 | 22/104                       |

features such as similarity to the most recently clicked listing (EmbClickSim) and similarity to the last long clicked listing (EmbLastLongClickSim). Due to the presence of these features, users can receive real-time feedback during the browsing process, and search results can change in real-time based on user click behavior.

After obtaining these embedding features, they are input into the search ranking model for training together with other features. Here, Airbnb uses a GBDT model that supports pairwise Lambda Rank [4] as the search ranking model, which has been open-sourced by Airbnb engineers. Finally, Table 8.5 shows the evaluation results of Airbnb's feature importance for reference.

