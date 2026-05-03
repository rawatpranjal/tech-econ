## 5.4.3.4 Multi-gate Mixture-of-Experts

Google  scientists  and  engineers  continued  to  advance  this  algorithm  and  created Multi-gate Mixture-of-Experts (MMoE) model [6]. MMoE uses as many gating networks as there are tasks (as shown in Figure 5.11(c)). This way, the weights for the expert networks are tailored individually to each task and therefore achieved selective utilization of experts. Consequently, the model becomes better equipped to capture the correlations and differences among subtasks.

Specifically, MMoE can be formulated as:

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Here, g k is the gating network for the k th subtask, and it can be expressed as:

<!-- formula-not-decoded -->

MMoE has largely improved the modeling process for multiple tasks, but it still has prominent shortcomings. First of all, the experts are shared by all tasks, and therefore cannot capture more complicated relationships between tasks and can bring noises for some tasks. In addition, the lack of interaction between experts can diminish the model's performance. To solve some of these problems, scientists and engineers from Tencent proposed another novel model for multi-task learning - Progressive Layered Extraction (PLE) [7].

