## 3.11.1 Relationship between BERT and Transformer

The BERT model is a specific implementation of the Transformer architecture, so it is actually one type Transformer model. But compared with the original Transformer model proposed in the 'Attention is All You Need' paper [18], the BERT model has the following differences:

- Model Structure: Instead of using both encoder and decoder stacks, BERT just used a stack of encoders in the model structure.
- Training: The training steps of a BERT model in an NLP application usually involve two steps of training - pre-training and fine-tuning. BERT uses Masked Language Model (MLM) objectives and task-specific objectives in the fine-tuning task. In pre-training, the MLM objective enables the BERT model to fuse both left and right contexts. This is also where 'bi-directional' is from, in the BERT model name.
- Model Usage: As the BERT model only includes encoder stacks, its direct output are vectors. As a result, the major applications of BERT model are embedding generations and classifications. However, the major use case for the Transformer model is sequence-to-sequence generation.

The  following  section  mainly  focuses  on  the  BERT  model's  applications  and  its derivatives in recommender systems.

