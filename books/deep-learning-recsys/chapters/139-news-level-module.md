## News-Level Module

The news-level module (NLM) aggregates the word's hidden representations of each news from the world-level module and feeds the aggregated vectors to multiple transformer layers to generate the final news representations and matching signal at the news level.

Three different aggregations were studied:

- (1)  The NSEP Aggregator directly used the generated embeddings of special tokens (NSEP) from the WLM output.
- (2)  The Mean Aggregator averages the word embeddings for each news segment.
- (3)  Attention Aggregators apply a lightweight attention network. The attention network applied a fully connected neural network with a tanh activation function. Then it  connects  with  another  fully  connected  neural  network  to  generate  the combination weights f . The weights then are applied in the linear combination of word embeddings as in Eq. 3.25,

<!-- formula-not-decoded -->

where the wi is the word embeddings from WLM for i -th word and S j is the j -th news representation.

