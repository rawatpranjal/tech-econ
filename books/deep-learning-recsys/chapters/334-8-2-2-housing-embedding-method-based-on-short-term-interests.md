## 8.2.2 Housing Embedding Method Based on Short-Term Interests

Airbnb uses the in-session click data to embed the listings, capturing the user's shortterm interests during a single search. The session click data refers to a sequence of listings that a user clicks during a single search, which must meet two conditions: (1) the user must stay on the listing detail page for more than 30 seconds to be counted as a data point in the sequence; (2) if the user has no action for more than 30 minutes, the sequence will be interrupted and is no longer considered a session. This is done for two purposes, which are to filter out noise and negative feedback signals, and to avoid the generation of nonrelevant sequences.

With the sequence of clicked listings, it is possible to embed them like a sentence sample, just like the Item2vec method described in Section 4.3. Airbnb chose the skipgram model from Word2vec, which was introduced in Section 4.2, as the framework

for the embedding method, modifying the objective function of Word2vec to approximate Airbnb's business objectives.

The method of Word2vec was introduced in detail in Section 4.1 of this book. Here, we list the objective function of the skip-gram model of Word2vec:

<!-- formula-not-decoded -->

After adopting the training method of negative sampling, the objective function is transformed into the following form,

<!-- formula-not-decoded -->

where σ is the sigmoid function, D is the positive sample set, and ′ D is the negative sample set. The first half of Equation 8.3 represents the objective function of the positive samples, while the second half represents the function of negative samples (with an added negative sign).

Returning to the Airbnb listing embedding problem, the positive samples in the embedding process are naturally taken from the listing within the sliding window of the click sequence in the session, while the negative samples are randomly selected from the corpus (that is, all the available listings) after determining the central listing.

Therefore,  Airbnb's  initial  objective  function  is  almost  identical  to  that  of Word2vec,

<!-- formula-not-decoded -->

On the top of original Word2vec embedding, Airbnb's engineers wanted to introduce historical booking information into the embedding process. This can make Airbnb's search results and similar listings more likely to recommend the items based on previous bookings. From this motivation, Airbnb divided session click sequences into two categories: booking sessions and exploratory sessions.

In each booking session, only the last item is the listing that is finally booked. In order to introduce this booking behavior into the objective function, whether the booked listing is in the Word2vec sliding window or not, it is assumed that the booked listing is related to the central listing in the sliding window. This introduces a global context into the objective function. Therefore, the objective function becomes as follows,

<!-- formula-not-decoded -->

In the last term, l b represents the booked listing, and because booking is a positive sample behavior, this term also has a negative sign in front of it. It should be noted that there is no Σ symbol in front of the last term like the preceding terms. It is because the central listing in the sliding window is related to all other listings in the sliding window.

To better discover the differences between listings within the same marketplace, Airbnb added another set of negative samples. These are randomly sampled from the set of listings in the same marketplace as the central listing. Similarly, they can be added to the objective function as follows,

<!-- formula-not-decoded -->

Among them,  mn refers to the collection of negative samples in the same region in the new dataset.

Thus, the objective function for the listing embeddings is defined, and the training process for the embeddings is the standard process of using negative sampling as in Word2vec, which will not be further elaborated here.

In addition, the paper also introduces a method to solve the cold start problem. In short, if there is a new housing missing an embedding vector, the average of the embedding vectors of three nearby housing units of the same type and similar price will be taken, which is a good practical engineering experience.

