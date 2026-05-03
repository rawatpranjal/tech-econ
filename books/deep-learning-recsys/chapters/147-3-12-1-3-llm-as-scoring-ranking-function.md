## 3.12.1.3 LLM as Scoring/Ranking Function

In this application, LLM is used to directly generate (1) the rating for the candidate item, (2) the recommendation list of the items, and (3) both rating and recommendation lists with a multitask setup.

In this section, we will briefly introduce one work by the Google team [21] and present an example of using LLM to finish the scoring task. In this work [21], authors explored the  LLM's ability  to  generate  ratings  with  zero-shot,  few-shot,  and  finetuned settings. The task is to predict users' ratings based on their viewing history.

The prompt design for zero-shot and few-shot are presented in Figure 3.40 (a) and (b), respectively. In the zero-shot prompt, the user's interaction history is just listed down with the user rating, whereas a few rating prediction examples are included in

Output

CHHI

Output

Few-Shot User Rating Predictor

Classification

4.0

Encoded Context

(b)

Output

(c)

Zero-Shot User Rating Predictor

(a)

Regression

00000}

.. Your diren he diets past rating history, in the formatt in the format: Tra, Genres, Raing.

Given a user's past movie ratings in the format: Title, Genres, Rating.

Ratings range from 1.0 to 5.0.

Q: The user history is:

