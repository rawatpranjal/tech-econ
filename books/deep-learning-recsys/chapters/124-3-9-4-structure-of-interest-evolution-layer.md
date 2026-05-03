## 3.9.4 Structure of Interest Evolution Layer

The  biggest  distinction  between  the  interest  evolution  layer  and  the  interest extraction layer is the addition of an attention mechanism. This mechanism is in the same vein as DIN. It can be seen from the connection of the attention units in

Figure  3.25.  The  generation  process  of  the  attention  score  of  the  interest  evolution layer is exactly the same as that of DIN, which is the result of the interaction between the current state vector and the target advertisement vector. That is to say, DIEN needs to consider the relevance of targeted advertisements in the process of simulating interest evolution.

This also answers the question at the end of Section 3.9.3. The interest evolution layer is added on top of the interest extraction layer in order to simulate the interest evolution path related to the target advertisement in a more targeted manner. Due to the characteristics of e-commerce such as Alibaba, users are very likely to purchase multiple categories of goods at the same time. For example, while purchasing a 'mechanical keyboard,' they are still viewing the goods under the 'clothing' category. As a result, the attention mechanism is particularly important under such condition. When the target advertisement is an electronic product, the interest evolution path related to the purchase of 'mechanical keyboard' is obviously more important than the evolution path of purchasing 'clothes.' Such distinction logic doesn't exist in the interest extraction layer.

The interest evolution layer achieves application of the attention mechanism by adopting the GRU with Attentional Update gate (AUGRU) structure. AUGRU adds the attention score to the structure of the update gate of the original GRU. The specific form is shown in Eq. 3.18:

<!-- formula-not-decoded -->

Comparing with Eq. 3.17, it can be seen that AUGRU adds the attention score a t on the basis of the original u t ′ , where u t ′ is the original update gating vector and similar to u t in Eq. 3.17. The generation method of the attention score is basically the same as that of DIN, which uses the attention activation units.

