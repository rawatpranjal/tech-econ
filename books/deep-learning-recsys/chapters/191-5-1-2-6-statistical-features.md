## 5.1.2.6 Statistical Features

Statistical features refer to features calculated by statistical methods, such as historical CTR, historical CVR, item popularity, and so on. Statistical features are generally continuous features, which can be directly input into the recommender system for training with standardization and normalization.

Statistical features are essentially some coarse predictors. For example, in the CTR prediction problem, the historical average CTR of an item can be viewed as the simplest prediction model, but the prediction ability of this model is very weak, so the historical average CTR is often only used as one of the features of a complex CTR model. Statistical features usually have a strong correlation with the final target, therefore they are an important feature category that should never be ignored.

