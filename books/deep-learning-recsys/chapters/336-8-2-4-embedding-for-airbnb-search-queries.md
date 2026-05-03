## 8.2.4 Embedding for Airbnb Search Queries

In addition to computing embeddings for users and listings, Airbnb also applied embeddings for search queries in its search recommender system. Similar to the method for user embeddings, the search queries and listings are embedded in the same vector space, and then sorted based on their cosine similarity. The search ranking generated using the embedding method differs from the traditional text similarity approach.

Before the introduction of embeddings, the search results could only be based on the input keywords. However, with the introduction of embeddings, the search results can even capture the semantic information of the search query. For example, when inputting 'France Skiing,' although none of the location names in the results contain the keyword 'Skiing,' the associated results are all ski resorts in France. This undoubtedly provides results that are closer to the user's intention.

