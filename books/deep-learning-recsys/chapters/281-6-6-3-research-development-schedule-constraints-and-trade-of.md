## 6.6.3 Research Development Schedule Constraints and Trade-Offs in Technology Selection

In the actual engineering environment, the constraints of the research and development schedule are also a factor that cannot be ignored. This involves the engineer's ability to control the overall project and to estimate the development timeline. No one wants to be the slowest link to drag down other teams in the IT industry, where product iterations are increasingly rapid.

In the process of upgrading the technology stacks, it is necessary to fully weigh the new requirements of the product and the progress of the overall migration. For example, the company hopes to migrate the machine learning platform from Spark to TensorFlow. This is a technical decision to follow the latest technological trends. However, due to the characteristics of the Spark platform, the programming   language and model training methods are quite different from TensorFlow. The entire   migration must be through a long development cycle. During the migration process, if there are new product requirements, engineers need to make trade-offs and take into account the daily development progress in the process of technology upgrade.

There are two possible technical paths:

- (1)  Let the entire team focus on completing the migration from Spark to TensorFlow, and then conduct research and development of new models and new functions on the new platform.
- (2)  Some team members use the mature and stable Spark platform to continue the development and quickly meet product requirements, leaving sufficient time for TensorFlow migration. At the same time, another group of members fully work on TensorFlow to ensure the maturity of the new platform before mass migration.

From a purely technical point of view, since it has been decided to migrate to the TensorFlow platform, theoretically there is no need to spend time developing new models using the Spark platform. However, we need to clarify two key considerations here:

- (1)  No matter how mature the platform is, it always takes a long time for the entire team to break in and conduct the tuning. It is impossible to let it support important business logic right after the migration.
- (2)  The technology platform migration is usually a technical decision and requires transparency with the other stakeholders. However, it should not be a direct reason for deprioritizing the business support.

Therefore, from the perspective of project progress and risk, the second technical path should be a more realistic choice for project development.

