## 5.4.3.1 Weighted Loss Function

To  solve  multi-task  learning  problems,  the  most  straightforward  approach  is  to create a weighted loss function. This approach is essentially combining multiple tasks into one task. It is easy to train and deploy, and the outcome is favorable by improving the outcome of the additional tasks without compromising the primary task. However, the weights of the additional tasks can be hard to determine and may require AB testing.

The loss function is shown in Equation 5.2:

<!-- formula-not-decoded -->

