## 5.7.1.3 UCB Algorithm

UCB is another classic heuristic exploration vs. exploitation algorithm. Similar to the idea of Thompson Sampling, both algorithms use the uncertainty of the distribution as the basis to determine the degree of exploration. But UCB is more convenient for engineering implementation. Here is the algorithm flow of UCB:

- (1)  Assuming that there are K slot machines, each slot machine is randomly selected m times, and the initial empirical mean x j of machine j 's reward is obtained.
- (2)  Use t to represent the total number of lever-pulls so far, use nj to represent the number of times the j th machine has been pulled so far, and calculate the UCB value of each machine:

<!-- formula-not-decoded -->

- (3)  Select the slot machine i with the largest UCB value, pull the lever, and observe its reward Xi,t .
- (4)  Update the expected reward x i of machine i according to Xi,t .
- (5)  Repeat steps 2 through 4.

The focus of the UCB algorithm is the calculation of the UCB value. In Equation 5.12, x j represents the expected reward from previous experiments of slot machine j ,

which can be regarded as the score of 'exploitation'; and 2log t n j is the width of the confidence interval, which represents the score of 'exploration.' The sum of the two is the upper bound of the confidence interval for slot machine j .

