---
title: "Observational Causal Inference"
date: 2024-12-21
category: "Causal Inference"
description: "How to estimate causal effects when you can't run an experiment"
tags: ["Causal Inference", "DiD", "Synthetic Control", "Matching", "Observational Studies"]
draft: false
---

## The Problem

Not everything can be A/B tested. Sometimes experiments are impossible (you can't randomly assign cities to policies), unethical (you can't withhold a beneficial treatment), or too slow (market changes won't wait for statistical significance).

**Observational causal inference** lets you estimate causal effects from non-experimental data—but it requires careful assumptions and methodology.

> **When You Can't Experiment**
> - **Policy changes:** Measuring the effect of a new law or regulation
> - **Market shocks:** Understanding impact of competitor entry or economic events
> - **Historical analysis:** Learning from past decisions without prospective randomization
> - **Ethical constraints:** When withholding treatment isn't acceptable

The fundamental challenge: correlation isn't causation. Users who see a promotion might buy more—but maybe they were already more likely to buy. Observational methods try to construct valid counterfactuals from non-random data.

Companies like Uber, DoorDash, and Meta use these techniques daily when experiments aren't feasible.

## Common Approaches

### 1. Difference-in-Differences (DiD)

The workhorse of policy evaluation. Compare the change in outcomes for a treated group vs. a control group, before and after treatment.

> "Difference-in-differences corrects pre-experiment bias between groups to produce reliable treatment effects estimation."
> — [Uber Engineering](https://www.uber.com/blog/xp/)

The key assumption: **parallel trends**. Without treatment, both groups would have followed the same trajectory. This is testable by examining pre-treatment periods.

**When to use:** Policy changes, feature rollouts to specific regions, natural experiments where timing varies.

### 2. Synthetic Control

When you have one treated unit (a city, country, or product) and need to construct a counterfactual from a weighted combination of control units.

> "Synthetic control methods find the optimal weighted combination of donor units that best matches the treated unit's pre-treatment trajectory."
> — [Meta's GeoLift](https://facebookincubator.github.io/GeoLift/)

The method became famous from Abadie's studies of California's tobacco program and German reunification. Now it's standard for geo-experiments at tech companies.

**When to use:** Geographic tests, single-unit interventions, marketing lift measurement.

### 3. Matching & Propensity Scores

Create comparable treatment and control groups by matching on observable characteristics. Propensity score matching estimates the probability of treatment, then matches units with similar scores.

The intuition: if two users have the same propensity to receive treatment but only one actually did, comparing their outcomes estimates the causal effect.

**When to use:** User-level observational data, when you have rich covariates, retrospective analysis of targeted interventions.

### 4. Regression Discontinuity (RDD)

Exploit sharp cutoffs in treatment assignment. If users above a threshold get treatment and those below don't, comparing outcomes just above and below the threshold estimates causal effects.

Examples: credit score cutoffs for loan approval, GPA thresholds for scholarships, age cutoffs for eligibility.

**When to use:** Any situation with a clear assignment threshold.

## Try It Yourself

Here's how to implement Difference-in-Differences. Install with `pip install pandas statsmodels`:

```python
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf

def difference_in_differences(df, outcome, treated_col, post_col, covariates=None):
    """
    Estimate treatment effect using Difference-in-Differences.

    Parameters:
    -----------
    df : DataFrame with panel data
    outcome : name of outcome variable
    treated_col : binary indicator for treatment group
    post_col : binary indicator for post-treatment period
    covariates : optional list of control variables

    Returns:
    --------
    Regression results with DiD estimate
    """
    # Create interaction term (the DiD estimator)
    df = df.copy()
    df['treated_x_post'] = df[treated_col] * df[post_col]

    # Build formula
    formula = f"{outcome} ~ {treated_col} + {post_col} + treated_x_post"
    if covariates:
        formula += " + " + " + ".join(covariates)

    # Fit OLS regression
    model = smf.ols(formula, data=df).fit(cov_type='cluster',
                                           cov_kwds={'groups': df['unit_id']})

    return model

# Example: Simulated policy evaluation
np.random.seed(42)

# Create panel data: 100 units, 10 time periods
n_units = 100
n_periods = 10
treatment_period = 5

data = []
for unit in range(n_units):
    # 50% of units are in treatment group
    treated = 1 if unit < 50 else 0
    base_outcome = np.random.normal(100, 10)  # unit fixed effect

    for t in range(n_periods):
        post = 1 if t >= treatment_period else 0

        # Outcome = base + time trend + treatment effect (if treated & post)
        outcome = (base_outcome +
                   t * 2 +  # common time trend
                   np.random.normal(0, 5) +  # noise
                   treated * post * 15)  # TRUE treatment effect = 15

        data.append({
            'unit_id': unit,
            'time': t,
            'treated': treated,
            'post': post,
            'outcome': outcome
        })

df = pd.DataFrame(data)

# Run DiD analysis
results = difference_in_differences(df, 'outcome', 'treated', 'post')
print(results.summary().tables[1])
```

**Expected output:**
```
                   coef    std err   t      P>|t|   [0.025   0.975]
Intercept        99.73      1.42   70.2    0.000   96.94   102.52
treated          -0.21      2.01   -0.1    0.917   -4.15     3.73
post              9.89      1.01    9.8    0.000    7.91    11.87
treated_x_post   15.12      1.43   10.6    0.000   12.32    17.92
```

**Key insight:** The `treated_x_post` coefficient (15.12) is our DiD estimate—very close to the true effect of 15!

For synthetic control, use Meta's GeoLift package or the `SyntheticControlMethods` Python library.

## Real-World Applications

| Company | How They Use Causal Inference |
|---------|-------------------------------|
| [Uber](https://www.uber.com/blog/causal-inference-at-uber/) | Uses DiD to correct pre-experiment bias in marketplace experiments. Mediation analysis reveals *why* treatments work. CausalML package for heterogeneous treatment effects. |
| [DoorDash](https://doordash.engineering/2022/06/14/leveraging-causal-inference-to-generate-accurate-forecasts/) | Combines DiD and synthetic control for demand forecasting. Back-door adjustment when A/B testing isn't possible due to regulatory constraints. |
| [Meta](https://facebookincubator.github.io/GeoLift/) | GeoLift package for geo-experiments using synthetic control. Essential for measuring ad effectiveness in post-cookie world. Powers marketing measurement across Meta's ad platform. |
| [Lyft](https://eng.lyft.com/causal-forecasting-at-lyft-part-1-14cca6ff3d6d) | Causal forecasting combines time series with intervention analysis. Switchback experiments for marketplace dynamics. |
| [Netflix](https://netflixtechblog.com/a-survey-of-causal-inference-applications-at-netflix-b62d25175e6f) | Instrumental variables for content recommendations. Quasi-experiments when full randomization isn't possible. |
| [Microsoft](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/) | EconML package for heterogeneous treatment effects. Double machine learning for high-dimensional confounders. |

## Further Reading

### Essential Reading
- [Causal Inference: The Mixtape](https://mixtape.scunning.com/) — Scott Cunningham's free online textbook with code examples
- [The Effect](https://theeffectbook.net/) — Nick Huntington-Klein's modern introduction
- [Mostly Harmless Econometrics](https://www.mostlyharmlesseconometrics.com/) — Angrist & Pischke's classic

### Tools & Libraries
- [DoWhy](https://github.com/py-why/dowhy) — Microsoft's causal inference library
- [EconML](https://github.com/py-why/EconML) — Heterogeneous treatment effects with ML
- [CausalML](https://github.com/uber/causalml) — Uber's uplift modeling package
- [GeoLift](https://github.com/facebookincubator/GeoLift) — Meta's geo-experimentation toolkit

### Courses
- [MIT 14.386: Econometrics](https://ocw.mit.edu/courses/14-386-new-econometric-methods-spring-2007/) — Graduate-level causal inference
- [Stanford STATS 361](https://web.stanford.edu/class/stats361/) — Causal Inference
- [Coursera: Causal Inference](https://www.coursera.org/learn/causal-inference) — UPenn's introductory course

### Key Researchers
- [Guido Imbens](https://www.gsb.stanford.edu/faculty-research/faculty/guido-w-imbens) — Nobel laureate, pioneer of modern causal inference
- [Susan Athey](https://athey.people.stanford.edu/) — Causal forests, machine learning for causal inference
- [Alberto Abadie](https://economics.mit.edu/people/faculty/alberto-abadie) — Inventor of synthetic control method

### Datasets for Practice
- [LaLonde Dataset](https://users.nber.org/~rdehejia/data/.nswdata2.html) — Classic job training program evaluation
- [Card & Krueger Minimum Wage](https://davidcard.berkeley.edu/papers/njmin-aer.pdf) — Famous DiD study data
- [California Tobacco Control](https://economics.mit.edu/people/faculty/alberto-abadie/research) — Original synthetic control application
