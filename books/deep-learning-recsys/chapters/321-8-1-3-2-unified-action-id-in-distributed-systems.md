## 8.1.3.2 Unified Action ID in Distributed Systems

In order to achieve the combination of impression data and click records in a distributed system, in addition to generating a globally unified request ID for each behavior, Facebook also established a HashQueue to cache the impression records. The impression in the HashQueue will be considered as a negative sample if no matching click data  is  found  within  the  waiting  window.  Facebook  uses  the  Scribe  framework  to implement this process. Some other companies use Kafka to cache the big data, and use stream computing frameworks such as Flink and Spark Streaming to complete subsequent real-time computing.

