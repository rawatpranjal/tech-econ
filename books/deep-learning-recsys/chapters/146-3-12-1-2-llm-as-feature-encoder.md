## 3.12.1.2 LLM as Feature Encoder

In this application, LLM is used as a feature encoder to encode the textual features and use the encoded representations in the recommendation model. The benefits of using a LLM as a feature encoder are:

- (1)  Enriching the user or item representations with more semantic meanings.
- (2)  Transferring generalized knowledge from a pretrained LLM foundation model for cross-domain or cold start recommendations.

The UNBERT model introduced in Section 3.11.2 falls within this bucket. In the UNBERT model, a pre-trained BERT is adopted in the Word Level Module to encode the concatenated texts for target news and user-interacted news. Readers can refer to Section 3.11.2 for more details.

