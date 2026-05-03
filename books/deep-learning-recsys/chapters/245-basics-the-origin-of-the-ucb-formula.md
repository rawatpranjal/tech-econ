## Basics: The Origin of the UCB Formula

So where does the UCB formula come from? In fact, the UCB formula is derived based on Hoeffding's inequality.

Suppose there are N independent bounded random variables ranging from 0 to 1, X 1 , X 2,…, Xn , then the empirical expectation of these n random variables is

<!-- formula-not-decoded -->

Subject to the inequality shown in Equation 5.13:

<!-- formula-not-decoded -->

This is Hoeffding's inequality.

So what is the relationship between Hoeffding's inequality and the upper bound of UCB? Let /g72 /g32 2log t n j , and substitute it into Equation 5.13, Hoeffding's inequality can be transformed into Equation 5.14:

<!-- formula-not-decoded -->

From Equation 5.14, we can see that if the upper bound of UCB is 2log t n j , then the probability that the difference between the mean value of X and the actual expected value of X is outside the upper bound is very small, less than t -4 , which means that using UCB for the upper bound is strict and reasonable.

The rigorous proofs for UCB can be much more theoretical and out of scope of this book. The point here is that the upper bound of UCB is equivalent to the strict confidence interval of the slot machine's expected reward.

Both  UCB  and  Thompson  Sampling  are  common  exploration  vs.  exploitation methods in engineering, but such traditional methods cannot solve the problem of adding personalized features. This severely limits the use of exploration vs. exploitation in personalized recommendation scenarios. Therefore, personalized exploration vs. exploitation methods are proposed.

