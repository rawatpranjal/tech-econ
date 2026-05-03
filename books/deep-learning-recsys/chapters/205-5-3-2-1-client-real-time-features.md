## 5.3.2.1 Client Real-Time Features

The client is the closest link to the user and is where the user's in-session behavior and all contextual characteristics can be collected in real-time. In a classic recommender system, it is a common way to request recommendation results by using the client to collect contextual features such as time, location, and recommendation scenarios, and then sending these features to the server along with the http request. But it is easily overlooked that the client is also where the user's behavior within the session can be collected in real-time.

In the case of a news app, the user clicks and reads three articles in one session (assuming a three-minute session). These three articles are crucial to the recommender system because they represent the user's immediate interests. If the recommendation results can be changed in real-time based on the user's immediate interests, it will be a good user experience for a news app.

If a traditional streaming computing platform (Flink in Figure 5.6) or even a batch computing platform (Spark in Figure 5.6) is used, due to latency issues, the system may not be able to retrieve and store the in-session behavior into a feature database (such as Redis) within three minutes. As a result, the user's recommendation list will not be immediately affected by the in-session behavior, and thus cannot achieve a real-time update of the recommendation results.

If the client can cache the in-session behavior and transmit it to the server in realtime like the context features, then the model can obtain the in-session behavior in real-time and make recommendations based on it. This is the advantage of using client real-time features for timely recommendations.

