## 5.4.3.3 Mixture-of-Experts

To solve this problem for less correlated tasks, the concept of soft parameter sharing is proposed, and Mixture-of-Experts (MoE) is a main method of soft parameter sharing [5]. For this approach (as shown in Figure 5.11(b)), a network constitutes a set of experts replaces the shared bottom, where each expert is a forward-feeding network. In addition, a gating network is used to control which of the experts should be used for each training case. MoE can be formulated as:

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Here, y k is the output of the k th subtask, f i ( i n /g32 /g125 1, , ) are the n expert networks, and g x i ( )  is the i th logit of the output of g x ( ) with g x i i n ( ) /g32 /g166 /g32 1 1. Here, g is the gating network, represented by a SoftMax layer of linear transformations from the input:

<!-- formula-not-decoded -->

The  function g generates  probability  distribution  for  the  n  experts,  and  outputs  a weighted sum of all the experts. MoE can be regarded as an ensemble of multiple independent models.

