## 4.1.2 Expansion of Embedding Application in Other Fields

Now that embedding can vectorize words, it can also generate vectorized representations for the items in other application domains in some way.

walked

For  example,  if  embedding  is  applied  to  movie  items,  the  distance  between Embedding(The Avengers) and Embedding(Iron Man) should be very close in the embedding vector space, while the distance between Embedding(The Avengers) and Embedding(Gone with the Wind) will be relatively far.

In the same way, if the product is embedded in the e-commerce scenarios, the vector distance between Embedding(keyboard) and Embedding(mouse) should be relatively close, while the distance between Embedding(keyboard) and Embedding(hat) will be relatively far.

Unlike word vectors that use a large text corpus for training, the training samples in different fields are different. For example, video recommendation often uses the user's  streaming  sequence  to  embed  movies,  while  e-commerce  platforms  use  the user's purchase history as training samples.

