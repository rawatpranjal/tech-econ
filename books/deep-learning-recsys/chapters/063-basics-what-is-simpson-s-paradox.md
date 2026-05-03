## Basics: What Is Simpson's Paradox?

When  conducting  group  research  on  a  sample  dataset,  the  group  that  has  the advantage in comparison sometimes loses in the overall evaluation. This counterintuitive phenomenon is called 'Simpson's paradox.' The following example of video recommendation will further illustrate what 'Simpson's Paradox' is.

Assume that Tables 2.1 and 2.2 show the data of videos clicked by male and female users:

We can see that both male and female users have a higher click-through rate on video B than video A. Apparently, the recommender system should prioritize its recommendation of video B to users.

Table 2.1 Male users

| Video   |   Click (count) |   Impression (count) |   CTR (%) |
|---------|-----------------|----------------------|-----------|
| Video A |               8 |                  530 |      1.51 |
| Video B |              51 |                 1520 |      3.36 |

Table 2.2 Female users

| Video   |   Click (count) |   Impression (count) |   CTR (%) |
|---------|-----------------|----------------------|-----------|
| Video A |             201 |                 2510 |      8.01 |
| Video B |              92 |                 1010 |      9.11 |

Table 2.3 All users combined

| Video   |   Click (count) |   Impression (count) |   CTR (%) |
|---------|-----------------|----------------------|-----------|
| Video A |             209 |                 3040 |      6.88 |
| Video B |             143 |                 2530 |      5.65 |

However, if we ignore gender, what conclusions can be drawn from the combined data (as shown in Table 2.3)?

Surprisingly, in the combined results, the click-through rate of video A is actually higher than that of video B. If a recommendation is made based on this, it will lead to the exact opposite conclusion from the previous results, which is the so-called Simpson's paradox.

In this example, the group experiment is equivalent to using the interacting feature of 'gender' + 'video id,' while the combined experiment uses the individual feature of 'video id' to calculate the click-through rate. The combined experiment reduces high-dimensional features and loses a lot of useful information, therefore unable to correctly characterize the data pattern.

Logistic  regression  only  performs  direct  weighting  on  individual  features,  and does not have the ability to interact with features to generate high-dimensional combined features, so its expressivity is weak, and it may even draw erroneous conclusions like 'Simpson's paradox.' Therefore, it is necessary and urgent to improve the LR model to enable the capability of feature interactions.

