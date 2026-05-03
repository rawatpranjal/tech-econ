## 3.9.3 Interest Extraction Layer

The basic structure of the interest extraction layer is a Gated Recurrent Unit (GRU) network.  Compared  with  the  traditional  sequence  model  RNN  (recurrent  neural network),  GRU  solves  the  vanishing  gradients  problem  commonly  seen  in  RNN. Compared with LSTM (long short-term memory network), GRU has fewer parameters and faster training convergence speed. All of the aforementioned reasons result in the final adoption of the GRU network in the DIEN model.

The specific form of each GRU unit is defined as:

<!-- formula-not-decoded -->

where σ is the sigmoid activation function,  is the element-wise product operation, W W W U U U u r h z r h , , , , , are  six  sets  of  parameter  matrices  to  be  learned. i t is  the input state vector, that is the embedding vector e t ( ) of each behavior in the behavior sequence layer. h t is the t th hidden state vector in the GRU network

Following the interest extraction layer with multiple GRUs, the user's behavior vector b ( ) t is  further  abstracted  to  form  the  interest  state  vector h ( ) t .  In  theory, based on the sequence of interest state vectors, the GRU network can already predict the next interest state vector, but why does DIEN further add the interest evolution layer?

