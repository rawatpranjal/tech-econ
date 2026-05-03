## 3.3.1 Application Scenarios of the Deep Crossing Model

The application scenario of the Deep Crossing model is the search advertisement recommendations in the Microsoft search engine Bing. After a user enters a search term in the search box, the search engine will not only return relevant results but also return advertisements related to the search term, which is also the main profit source of most search engines. Based on the business model, the most important module of an ads system is to build a CTR model to accurately predict click-through rate and further lift performance of ads recommendation. Therefore, CTR naturally become the optimization objective of the Deep Crossing model.

The features used by Microsoft under this use case are shown in Table 3.1. These features can be divided into three categories - the categorical features that can be processed into one-hot or multi-hot vectors, including user search terms (that is, query), ad keyword, ad title, landing page, match type; the numeric features, which Microsoft calls counting features, including CTR and click prediction; the other one is the features that need further processing, including advertising campaign, impression, click, and so on. Strictly speaking, these are not independent features but rather a group of features that need further processing. For example, the budget in the advertising campaign can be used as a numerical feature, and the ID of the advertising plan can be used as a categorical feature.

Categorical  features  can  be  processed  into  feature  vectors  through  one-hot or  multi-hot encoding, and numerical features can be directly concatenated into

Table 3.1 Features in the Deep Crossing model

| Feature           | Feature meaning                                                                                                      |
|-------------------|----------------------------------------------------------------------------------------------------------------------|
| Search term       | The search term entered by the user in the search box                                                                |
| Ad keyword        | Keywords that the advertiser adds to the ad to describe their product                                                |
| Ad title          | The titles of the ads                                                                                                |
| Landing page      | The first page after ad is clicked                                                                                   |
| Match type        | Advertiser-selected ad-search term match type (including exact match, phrase match, semantic match, and so on)       |
| CTR               | Ad's historical CTR                                                                                                  |
| Click prediction  | CTR prediction from another CTR model                                                                                |
| Ad campaign       | The ad delivery plan created by the advertiser, including budget, targeting conditions, and so on                    |
| Impression Sample | An example of an ad 'impression' that records the contextual information about the ad in the actual impression scene |
| Click Sample      | An example of an ad 'click' that records the contextual information about the ad in the actual click scenario        |

Objective

Scoring Layer feature vectors. After generating the vector representation of all input features, the Deep Crossing model uses the feature vectors to predict CTR. The characteristic of a deep learning network is that the network structure can be flexibly adjusted according to the business and engineering needs, so as to achieve the end-to-end training from the original input features to the final optimization target. Next, by analyzing the network structure of the Deep Crossing model, we can explore how deep learning can accurately predict the CTR through the layer-by-layer processing of features.

