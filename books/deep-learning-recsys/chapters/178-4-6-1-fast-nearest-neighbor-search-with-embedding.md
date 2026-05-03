## 4.6.1 Fast Nearest Neighbor Search with Embedding

The  traditional  calculation  method  of  embedding  similarity  is  to  apply  the  inner product  operation  between  user  and  item  embedding  vectors.  This  means  that  in order to retrieve a user's Top N relevant items, it is necessary to traverse all the items in the candidate set. Assuming that the embedding space has k dimensions and the candidate set size is n , then the time complexity of traversing all the items in the candidate set is O kn ( ). In a practical recommender system, the total number of candidate items n can easily reach the order of millions. So the time complexity of this traverse step is unbearable and will lead to significant latency in the online model inferencing process.

Let's think about this process from a different angle. Since the embedding of the user and the item is in the same vector space, the process of retrieving the most relevant item to the user using the embedding vector is actually a process of searching for the nearest neighbor in this vector space. If you can find a way to quickly search for the nearest neighbors in a high-dimensional space, then the embedding fast search problem can also be solved.

The nearest neighbor search by establishing a k-dimension tree (that is, k-d tree) structure is commonly used for the fast nearest neighbor search method, and the time complexity can be reduced to O n (log ) 2 . However, the structure of the k-d tree is more complex, and it often needs backtracking when searching for the nearest neighbors to  ensure the results are always the closest, which makes the search process more complicated. Moreover, the time complexity of O n (log ) 2 is not ideal. So is there a way with lower time complexity and easier operation? Next, we introduce the stateof-the-art fast nearest neighbor search method for the embedding space in practical recommender systems - Locality Sensitive Hashing (LSH) [12].

b

