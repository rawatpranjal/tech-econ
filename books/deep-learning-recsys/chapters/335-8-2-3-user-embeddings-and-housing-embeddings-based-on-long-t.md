## 8.2.3 User Embeddings and Housing Embeddings Based on Long-Term Interests

Short-term interest embeddings use user click data to construct housing embeddings, which can effectively find similar housing units, but are deficient in that they do not include users' long-term interest information. For example, if a user booked a housing unit six months ago, it includes the user's long-term preferences for attributes such as housing prices and types. However, because the previous embeddings only used session-level click data, they lost the user's long-term interest information.

To capture users' long-term preferences, Airbnb uses booking session sequences. For example, if user j has booked five housing units in the past year, then their booking session would be s l l l l l j j j j j j = ( ) , , , , 1 2 3 4 5 .  Since  there  is  a  set  of  booking  sessions, can we apply Word2vec's method to embeddings as we did with click sessions? The answer is no, because we would encounter a very tricky problem of data sparsity.

Specifically, the data sparsity problem of booking sessions manifests itself in the following three ways:

- (1)  The total number of booking behaviors is much smaller than the number of click behaviors, so the size of the booking session set is much smaller than that of the click session set.

- (2)  The number of booking behaviors for a single user is very small. Many users only booked one housing unit in the past year, which means that many booking session sequences have a length of only one.
- (3)  Most housing units are booked very few times. To train meaningful and stable embeddings using Word2vec, an item needs to appear at least 5-10 times, but many housing units are booked less than five times, which makes it impossible to obtain effective embeddings.

How to solve such a serious data sparsity problem and train meaningful user and housing  embeddings?  Airbnb's  solution  is  to  aggregate  similar  users  and  similar housing units based on certain attribute rules. For example, housing unit attributes are shown in Table 8.2.

You can use attribute names and bucket IDs (referring to the index number of attribute values) to form an attribute identifier. For example, if a listing is located in the US, has a listing type of 'Ent' (bucket 1), and a nightly price range of $56-59 (bucket  3),  you  can  use  'US\_lt1\_pn3'  to  represent  the  attribute  identifier  of  this listing.

The definition of user attributes follows the same logic. As shown in Table 8.3, user attributes include device type, whether the user has filled in a profile, whether they have a profile picture, and their history of bookings. These user attributes are fundamental and can be used to generate a user attribute identifier (or user type) using the same method as for listing attribute identifiers.

Table 8.2 Housing attributes

| Bucket ID                                                       | 1                 | 2                     | 3                      | 4               | 5         | 6          | 7          | 8      |
|-----------------------------------------------------------------|-------------------|-----------------------|------------------------|-----------------|-----------|------------|------------|--------|
| Country Listing Type Price per Night Num of Beds 5-star rating% | US Ent <40 1 0-40 | CA Priv 40-55 2 41-60 | GB Share 56-69 3 61-90 | FR 70-83 4+ 90+ | MX 84-100 | AU 101-129 | ES 130-189 | … 190+ |

Table 8.3 User attributes

| Bucket ID                 | 1     | 2                   | 3     | 4           | 5      | 6       | 7       |
|---------------------------|-------|---------------------|-------|-------------|--------|---------|---------|
| Market Device Full        | SF En | NYC Es Msft No No 1 | LA Fr | PHL Jp iPad | AUS Ru | LV Ko   | … De …  |
| Language                  |       |                     |       |             |        |         |         |
| Type                      | Mac   |                     | Andr  |             | Tablet | iPhone  |         |
| Profile                   | Yes   |                     |       |             |        |         |         |
| Profile Photo             | Yes   |                     |       |             |        |         |         |
| Num of Historical Booking | 0     |                     | 2-7   | 8+          |        |         |         |
| Price Per Night           | <40   | 40-55               | 56-69 | 70-83       | 84-100 | 101-129 | 130-189 |

With  user  and  listing  attributes,  a  new  booking  session  sequence  can  be re-generated through the aggregation of data. User attributes can directly replace the original user ID, generating a booking sequence consisting of all historical bookings for that particular user. This method solves the problem of sparse user booking data.

After  obtaining  the  booking  sequence  for  a  certain  user  attribute,  how  can  the embeddings for user and listing attributes be obtained? To ensure user attribute ID and listing attribute ID embeddings generated in the same vector space, Airbnb uses a somewhat counterintuitive method.

For a booking session ( ) , , , l l l m 1 2 … sorted by time for a given user ID, the original listing item is replaced by a tuple (user\_type, listing\_type), resulting in the sequence ( ) ( , ), ( , ), , ( , ) u l u l u l M M type type type type type type 1 1 2 2  . Here, l type1 refers to the listing attribute corresponding to listing l 1 ,  and u type1 refers to the user attribute at the time of booking listing l 1 . Since a user's attributes can change over time, u u type type 1 2 , may not be the same even they are from the same user.

Once the sequence is defined, the next question is how to train embeddings so that user and listing attribute embeddings can be in the same vector space. The training objective function used is completely in line with the form of the objective function defined in Section 8.2.2. However, since the (user type, listing type) tuple is used to replace the original listing, determining the 'central item' becomes a critical issue. In fact, Airbnb did not disclose the technical details in the related paper, but based on its general description, this section presents a training method that is closest to the original paper.

Airbnb provides the objective functions for training user type embeddings and listing type embeddings when the 'central item' in the sliding window is user type ( ) u t and listing type ( ) l t , respectively,

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

where D book is the set of user and listing attributes near the central item. Therefore, during the training process, user and listing attributes are treated equally, and these two target functions are exactly the same.

It can be said that Airbnb flattened all the tuples in the training process, treating user and listing attributes equivalently when training embeddings, ensuring that they naturally generate in the same vector space. Although this process wastes some information from two types of attributes, it is a good engineering solution.

Once the objective function for embedding is defined, and both user and listing embeddings are mapped to the same vector space, training can be conducted using Word2vec negative sampling. The cosine similarity between user and listing embeddings represents the user's long-term interest preference for a certain listing.

