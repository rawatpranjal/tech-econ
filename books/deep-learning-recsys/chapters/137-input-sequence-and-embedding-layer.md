## Input Sequence and Embedding Layer

The input sequence construction and embedding layers are illustrated in Figure 3.35. It includes 'News Sentence' and 'User Sentence,' where the News Sentence is simply  the  text  description  of  the  candidate  news  item,  and  the  User  Sentence  is  the concatenation of the news sequence that the user clicked in the history. The historical news items are  separated  by  a  special  segment  token  (NSEP).  Each  clicked  news is  also  represented by some text-based descriptions. The News Sentence and User Sentence are separated by another special token (SEP). Additionally, a classification token (CLS) is added at the beginning of concatenated sequence to help generate the classification embedding e w as shown in Figure 3.34.

There  are  four  layers  of  embeddings  generated  for  each  token  -  token  embedding, segment embedding, position embedding, and news segment embedding. The token, segment, and position embeddings are trained using masked LM, and segment embedding is randomly initialized and further updated in the fine-tuning task. The final input token representation Et is constructed by summing all four embeddings.

