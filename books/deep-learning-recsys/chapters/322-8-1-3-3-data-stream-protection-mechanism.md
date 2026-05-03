## 8.1.3.3 Data Stream Protection Mechanism

Facebook specifically mentioned the protection mechanism of the online data joiner. Once the data joiner fails due to some abnormality (for example, the click data stream cannot be correctly joined with the impression data stream due to a bug in the action

115%

110%

105%

100%

95%

90%

85%

80%

• Calibration

Relative NE

ID generation), all samples will become negative samples. Since the model is trained and served in real-time, the accuracy of the model will be immediately affected by the wrong sample data, which will directly affect advertising and company profits. The consequences are very serious. To this end, Facebook has specially set up an anomaly detection  mechanism.  Once  the  data  distribution  of  the  real-time  sample stream changes, it will immediately cut off the online learning process to prevent the prediction model from being affected.

