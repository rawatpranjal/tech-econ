## 5.1.1 Feature Engineering in Recommender Systems

In  recommender  systems,  the  core  of  features  represents  the  relevant  information about  certain  behaviors.  While  making  recommendations,  behaviors  must  be  converted  into  numerical  values  before  they  can  be  learned  by  the  machine  learning model. Therefore, the information from these behaviors must be extracted into features, and use multidimensional features to represent the behavior.

Information loss is inevitable during the process of converting the actual behavior to some abstract features. Firstly, in the actual recommendation scenario, there is usually a large amount of information, including contexts, images, and status. It is impossible to store all this information due to its massive data volume. Secondly, lots of this information is redundant and unusable. Taking excessive unrelated information into the model can inhibit the generalization ability of the model. Because of these two reasons, feature engineering in recommender systems needs to obey the following principle:

The goal of feature engineering is to extract a set of features so that it retains as much useful information as possible while eliminating redundant information in the behavior.

For example, while making a movie recommendation, how should the features be extracted to model the behavior of 'the user clicks on a movie'?

To answer this question, let's put ourselves in the user's shoes. What factors could influence our choice to click on a certain movie while viewing a list of movies? Here, we came up with this list of six factors ranked by their importance:

- (1)  Preferences on the movie genres.
- (2)  Popularity of the movie.
- (3)  Whether there is a favorite actor or director in the movie.
- (4)  Attractiveness of the movie poster.
- (5)  Whether watched the movie before.
- (6)  Mood at the moment.

Following the principle of 'retaining as much of the useful information as possible,' when extracting features for a movie recommendation, the features should be able to retain the information of these six factors as much as possible. Table 5.1 shows the factors and their corresponding useful information and features.

It is worth mentioning that in the process of feature extraction, it is inevitable to lose some information. For example, the factor of 'mood at the moment' is discarded. For another example, inferring the user's preferences from his/her viewing history

Table 5.1 Factors, useful information, and features

| Factors                                                    | Useful Information            | Features                                                                  |
|------------------------------------------------------------|-------------------------------|---------------------------------------------------------------------------|
| Preferences on the movie genres                            | List of movies watched        | Features of the movie id, or further generate interest embedding features |
| Popularity of the movie                                    | Popularity score of the movie | Popularity features                                                       |
| Whether there is a favorite actor or director in the movie | Metadata of the movie         | Labels in the metadata                                                    |
| Attractiveness of the movie poster                         | Image of the movie poster     | Image features                                                            |
| Whether watched the movie before                           | Movie watching history        | Boolean values for 'watched or not'                                       |
| Mood at the moment                                         | N/A                           | N/A                                                                       |

will also lead to information loss. Therefore, it is a realistic engineering practice to retain useful information based on available data to the fullest extent.

