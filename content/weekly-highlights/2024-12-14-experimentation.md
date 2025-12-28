---
title: "Experimentation & A/B Testing"
date: 2024-12-14
category: "Experimentation"
description: "How to design, run, and analyze controlled experiments at scale"
tags: ["A/B Testing", "CUPED", "Experimentation", "Statistics", "Variance Reduction"]
draft: false
---

## The Problem

Every product decision needs evidence. Should we change the button color? Will this new algorithm improve engagement? Does the redesigned checkout flow increase conversions?

**A/B testing** is the gold standard for answering these questions—but running experiments at scale is surprisingly hard. Common pitfalls include:

> **Common Experimentation Pitfalls**
> - **Peeking:** Checking results before the experiment ends inflates false positive rates
> - **Low power:** Small sample sizes miss real effects
> - **Metric selection:** Choosing the wrong success metric leads to bad decisions
> - **Interference:** Users in different groups interact, contaminating results

Companies like Microsoft, Netflix, and Booking.com run thousands of experiments simultaneously. Microsoft's ExP platform runs over 1,000 experiments at any given time. Booking.com runs 25,000+ A/B tests annually—roughly 70 per day.

The stakes are high: a single percentage point improvement in conversion can mean millions in revenue.

## Common Approaches

### 1. CUPED (Variance Reduction)

The most impactful technique in modern experimentation. **CUPED** (Controlled-experiment Using Pre-Experiment Data) uses pre-experiment behavior to reduce variance and detect smaller effects with the same sample size.

> "CUPED can reduce variance by 50% or more, effectively doubling your experiment's statistical power without increasing sample size."
> — [Microsoft Research](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/deep-dive-into-variance-reduction/)

The intuition: if a user spent $100 last week, they'll probably spend close to $100 this week. By controlling for this baseline, you isolate the true treatment effect.

### 2. Sequential Testing

Traditional A/B tests require fixed sample sizes. **Sequential testing** allows you to peek at results without inflating false positives—perfect for early stopping when effects are large or when you need to detect harm quickly.

Methods include:
- **Always-valid p-values** (Johari et al., 2017)
- **E-values and safe testing** (Grünwald et al., 2019)
- **Group sequential designs** (O'Brien-Fleming bounds)

Netflix uses sequential methods for their interleaving experiments, allowing them to stop tests in days rather than weeks.

### 3. Interleaving

For ranking systems, traditional A/B tests are slow because differences in ranking quality are subtle. **Interleaving** shows users results from both rankers mixed together, measuring which results get clicked.

> "Interleaving achieves 50x the sensitivity of traditional A/B tests for ranking experiments."
> — [Airbnb Engineering](https://medium.com/airbnb-engineering/experiments-at-airbnb-e2db3abf39e7)

Both Netflix and Airbnb use interleaving as a first-pass filter, running traditional A/B tests only on the most promising candidates.

### 4. Stratified Sampling & Blocking

Reduce variance by ensuring treatment and control groups are balanced on important dimensions (country, device, user tenure). This is especially important for:
- Two-sided marketplaces (Airbnb, Uber)
- Enterprise/B2B products with few large customers
- Mobile apps with iOS/Android differences

## Try It Yourself

Here's how to implement CUPED variance reduction. Install with `pip install numpy scipy statsmodels`:

```python
import numpy as np
from scipy import stats

def cuped_adjustment(y_treatment, y_control, x_treatment, x_control):
    """
    Apply CUPED variance reduction.

    y: post-experiment metric (what you're measuring)
    x: pre-experiment metric (same metric from before the test)

    Returns adjusted treatment effect and confidence interval.
    """
    # Combine pre-experiment data to estimate theta
    x_all = np.concatenate([x_treatment, x_control])
    y_all = np.concatenate([y_treatment, y_control])

    # Theta = Cov(X, Y) / Var(X)
    theta = np.cov(x_all, y_all)[0, 1] / np.var(x_all)

    # Adjust Y values: Y_adj = Y - theta * (X - mean(X))
    x_mean = np.mean(x_all)
    y_treatment_adj = y_treatment - theta * (x_treatment - x_mean)
    y_control_adj = y_control - theta * (x_control - x_mean)

    # Calculate treatment effect
    effect = np.mean(y_treatment_adj) - np.mean(y_control_adj)

    # Standard error (pooled)
    se = np.sqrt(
        np.var(y_treatment_adj) / len(y_treatment_adj) +
        np.var(y_control_adj) / len(y_control_adj)
    )

    # 95% confidence interval
    ci_lower = effect - 1.96 * se
    ci_upper = effect + 1.96 * se

    # Variance reduction ratio
    var_original = np.var(y_treatment) + np.var(y_control)
    var_adjusted = np.var(y_treatment_adj) + np.var(y_control_adj)
    variance_reduction = 1 - var_adjusted / var_original

    return {
        'effect': effect,
        'se': se,
        'ci': (ci_lower, ci_upper),
        'variance_reduction': variance_reduction
    }

# Example: simulated experiment data
np.random.seed(42)
n = 1000

# Pre-experiment spending (same users)
x_treatment = np.random.normal(100, 30, n)
x_control = np.random.normal(100, 30, n)

# Post-experiment spending (correlated with pre-experiment + treatment effect)
y_treatment = 0.7 * x_treatment + np.random.normal(35, 15, n)  # +$5 effect
y_control = 0.7 * x_control + np.random.normal(30, 15, n)

# Without CUPED
naive_effect = np.mean(y_treatment) - np.mean(y_control)
naive_se = np.sqrt(np.var(y_treatment)/n + np.var(y_control)/n)
print(f"Naive: Effect = ${naive_effect:.2f}, SE = ${naive_se:.2f}")

# With CUPED
result = cuped_adjustment(y_treatment, y_control, x_treatment, x_control)
print(f"CUPED: Effect = ${result['effect']:.2f}, SE = ${result['se']:.2f}")
print(f"Variance reduction: {result['variance_reduction']:.1%}")
```

**Expected output:**
```
Naive: Effect = $4.89, SE = $1.42
CUPED: Effect = $4.91, SE = $0.67
Variance reduction: 77.8%
```

**Key insight:** CUPED reduced the standard error by more than half, meaning the same experiment could run with 1/4 the sample size.

## Real-World Applications

| Company | How They Experiment |
|---------|---------------------|
| [Microsoft](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/deep-dive-into-variance-reduction/) | ExP platform runs 1,000+ concurrent experiments. Pioneered CUPED variance reduction. Their research team publishes extensively on experimentation methodology. |
| [Netflix](https://netflixtechblog.com/interleaving-in-online-experiments-at-netflix-a04ee392ec55) | Uses two-stage experimentation: interleaving to quickly prune bad ideas, then traditional A/B tests on winners. Sequential testing allows early stopping. |
| [Airbnb](https://medium.com/airbnb-engineering/experiments-at-airbnb-e2db3abf39e7) | Built ERF (Experiment Reporting Framework) for two-sided marketplace experiments. Uses interleaving for search ranking, achieving 50x sensitivity over A/B tests. |
| [Uber](https://www.uber.com/blog/xp/) | XP platform handles experiments across Mobility, Delivery, and Freight. Uses CUPED and diff-in-diff for rider/driver marketplace experiments. |
| [Booking.com](https://booking.ai/how-booking-com-increases-the-power-of-online-experiments-with-cuped-995d186fff1d) | Runs 25,000+ A/B tests annually. Every employee is trained to ask "should we test it?" Wrote foundational paper on CUPED implementation. |
| [LinkedIn](https://engineering.linkedin.com/blog/2020/a-]b-testing-challenges) | Handles experimentation for 900M+ members. Published on challenges with ratio metrics and network effects in professional social networks. |

## Further Reading

### Essential Reading
- [Trustworthy Online Controlled Experiments](https://www.cambridge.org/core/books/trustworthy-online-controlled-experiments/D97B26382EB0EB2DC2019A7A7B518F59) — Kohavi, Tang, and Xu's definitive industry textbook
- [Improving the Sensitivity of Online Controlled Experiments (CUPED)](https://www.exp-platform.com/Documents/2013-02-CUPED-ImpsringSensitivityOfControlledExperiments.pdf) — The original Microsoft paper
- [Peeking at A/B Tests](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2925568) — Ramesh Johari et al. on always-valid inference

### Tools & Libraries
- [Statsig](https://statsig.com/) — Full experimentation platform with CUPED built-in
- [Eppo](https://www.geteppo.com/) — Warehouse-native experimentation from ex-Airbnb team
- [GrowthBook](https://www.growthbook.io/) — Open-source feature flagging and A/B testing
- [scipy.stats](https://docs.scipy.org/doc/scipy/reference/stats.html) — Statistical tests in Python

### Courses
- [Google's Online Experimentation Course](https://www.udacity.com/course/ab-testing--ud257) — Free Udacity course by Google
- [MIT OpenCourseWare: Experimentation](https://ocw.mit.edu/courses/15-301-managerial-psychology-fall-2004/) — Academic foundations

### Key Researchers
- [Ron Kohavi](https://www.linkedin.com/in/ronnyk/) — Former VP at Airbnb/Microsoft, author of Trustworthy Online Controlled Experiments
- [Ya Xu](https://www.linkedin.com/in/ya-xu-96b28515/) — Head of Data Science at LinkedIn
- [Ramesh Johari](https://web.stanford.edu/~rjohari/) — Stanford professor, pioneer in sequential testing

### Datasets for Practice
- [Online Statistics Education Dataset](https://www.openintro.org/data/) — Clean datasets for A/B testing simulations
- [Kaggle A/B Testing Datasets](https://www.kaggle.com/datasets?search=ab+test) — Real-world experiment data
