## 5.3.2.3 Full Feature Processing of Distributed Batch Processing Platform

As the data eventually reaches the distributed storage system dominated by HDFS, distributed batch computing platforms such as Spark can finally calculate and extract full features. This stage also focuses on data manipulations such as joining multiple data sources and merging delayed signals.

The user's impression, click, and conversion data often arrive at HDFS at different times. The conversion data of some game apps can even be delayed by several hours. Therefore, full data batch processing is the only stage that can handle the extracting and merging of all features and corresponding labels. Higher-order feature combination is also a task that requires the readiness of all features, which is often impossible on client or streaming computing platforms.

Here are some main uses of the computing results from the distributed batch processing platform:

- (1)  Model training and offline evaluation.
- (2)  The features are stored in the feature database for subsequent online recommendation models.

From  data  generation  to  complete  loading  into  HDFS,  along  with  the  calculation delay of Spark, the total delay of this process often takes hours, and will by no means meet the requirement of 'real-time' recommendation. Therefore, it can only provide more accurate recommendations when the user logs in next time.

