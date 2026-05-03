## Click Predictor

The click predictor module takes the word-level matching signal e w from WLM and news-level matching signal e n from NLM to generate the user click probability of each item. The prediction function is as follows,

<!-- formula-not-decoded -->

In the UNBERT training, the pre-trained bert-base-uncased model weight is used directly to initialize the word-level module. Then, the entire model was fine-tuned using the MIND datasets - a real-world news recommendation dataset collected from MSN News logs.

News Sentence

Trump defeat

ETrump

Edefeat

[SEP]

ESEP)

American

EAme...

news

Enews

User Sentence

[NSEP]

US

election

ENSEP

Eus

Elec...

INSEP]

INSEP

april

E

april movie

Enovie

Since the UNBERT model has used a pre-trained BERT model as the foundation model, so it can capture some generalized knowledge outside the fine-tuning dataset. As a result, the UNBERT model has proved excellent performance on cold-start items. This strength is very beneficial for News recommender systems as there are tons of new news generated every day. Considering the importance of news freshness to the user, it is very important that the model can pick up new news items from the candidate pools and recommend to the relevant user in a timely way.

