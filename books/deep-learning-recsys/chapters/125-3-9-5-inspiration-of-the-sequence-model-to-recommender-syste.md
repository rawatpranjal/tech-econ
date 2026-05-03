## 3.9.5 Inspiration of the Sequence Model to Recommender Systems

This  section  introduces  Alibaba's  recommendation  model  DIEN  that  incorporates sequence models. Because the sequence model has a strong ability to express time series, it is very suitable for predicting the user's next action after a series of behaviors.

In fact, it is not only Alibaba that has successfully applied the sequence model to its e-commerce recommendation model, but video streaming companies such as YouTube and Netflix have also successfully applied the sequence model to their video recommendation models to predict the user's next streaming preferences (such as next watch).

However, it is necessary to pay attention to the high training cost of the model and the latency in online inferencing caused by serial prediction in a large sequence model. The complexity of sequence model undoubtedly increases the difficulty of its  productization.  So  system  optimization  turns  very  important  in  the  engineering implementation. Experiences with implementing a sequence model in production will be discussed in Chapter 8.

