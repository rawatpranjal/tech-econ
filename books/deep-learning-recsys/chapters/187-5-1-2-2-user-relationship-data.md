## 5.1.2.2 User Relationship Data

The internet is essentially the connection between people and information. If user behavior data is a log of 'connection' between people and things, then user relationship data records connections among people. In the age of the internet, one common phrase that people say is 'birds of a feather flock together.' User relationship data is undoubtedly valuable information for recommender systems to utilize.

User relationship data can also be divided into 'explicit' and 'implicit' types, or called 'strong relationship' and 'weak relationship.' As shown in Figure 5.1, users can  establish  a  'strong  relationship'  through  'following,'  'friendship,'  and  other connections, and they can also be in a 'weak relationship' by 'liking each other,' 'being in the same community,' or even 'watching a movie together.'

In recommender systems, there are many ways to utilize user relationship data. It can be used in the retrieval layer to retrieve items; it can also be used to establish a

Table 5.3 Classification and sources of attributes and labels

| Subject   | Category                                                                                    | Source                                                                                  |
|-----------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| User      | Demographic attributes (gender, age, address, and so on) Label of user interest             | User registration information, third- party DMP (Data Management Platform) User choices |
| Item      | Label of the item                                                                           | Added by user or system administrator                                                   |
|           | Item attributes (product category, price; movie category, year, actor, director, and so on) | Background entry, third-party database                                                  |

relationship graph, and generate embedding of users and items through graph embedding methods. Another utilization is to create new attribute features for users through the characteristics of their 'friends' directly from relationship data. It is even possible to build a social recommender system with user relationship data.

