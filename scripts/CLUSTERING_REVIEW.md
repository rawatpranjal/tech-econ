# Package Clustering Review - Full Cluster-by-Cluster Analysis

**Date**: 2026-01-05
**Reviewer**: Claude (with human oversight)
**Status**: In Progress

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total clusters defined | 38 |
| Clusters with enough items (≥4) | 37 |
| Filtered out (< 4 items) | 1 (pkg-automl) |
| Total packages in clusters | 519 rows (with duplicates) |
| Unique packages | ~188 |

---

## Cluster-by-Cluster Review

### Legend
- ✅ = Correct assignment
- ⚠️ = Questionable, needs review
- ❌ = Wrong assignment, needs fix
- 📝 = Note/observation

---

## CAUSAL INFERENCE (10 clusters)

### 1. pkg-did-synth (DiD & Synthetic Control)
**Count**: 39 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| pycinc | ✅ | DiD for continuous treatment |
| scpi | ✅ | Synthetic control prediction intervals |
| DRDID | ✅ | Doubly robust DiD |
| trimmed_match | ✅ | Geo experiment matching |
| matched_markets | ✅ | GeoLift companion |
| didet | ✅ | DiD estimation |
| microsynth | ✅ | Micro synthetic control |
| augsynth | ✅ | Augmented synthetic control |
| SCtools | ✅ | SC utilities |
| TFP CausalImpact | ✅ | TensorFlow version |
| pyleebounds | ✅ | Lee bounds for attrition |
| didhetero | ✅ | Heterogeneous DiD |
| mlsynth | ✅ | ML synthetic control |
| synthlearners | ✅ | Synthetic learners |
| GeoLift | ✅ | Geo experiments |
| gsynth | ✅ | Generalized synth |
| CausalImpact | ✅ | R version |
| csdid | ✅ | Callaway-Sant'Anna DiD |
| tidysynth | ✅ | Tidy synth |
| synthdid | ✅ | Synthetic DiD |
| pensynth | ✅ | Penalized synth |
| SyntheticControlMethods | ✅ | SC methods |
| pysyncon | ✅ | Python synth |
| bacondecomp | ✅ | Goodman-Bacon decomp |
| CausalPy | ✅ | DiD/SC in PyMC |
| Synth | ✅ | Original R synth |
| did | ✅ | Callaway-Sant'Anna |
| HonestDiD | ✅ | Sensitivity analysis |
| staggered | ✅ | Staggered DiD |
| fect | ✅ | Fixed effects counterfactual |
| fastdid | ✅ | Fast DiD |
| didimputation | ✅ | DiD imputation |
| Differences | ✅ | DiD package |
| fixes | ✅ | Fixed effects/event study |
| eventstudyr | ✅ | Event study |

**Verdict**: ✅ All correct

---

### 2. pkg-structural-estimation (Structural Econometrics)
**Count**: 30 items | **Status**: ⚠️ One issue

| Package | Status | Notes |
|---------|--------|-------|
| dcegm | ✅ | Discrete choice EGM |
| respy | ✅ | Keane-Wolpin estimation |
| Greeners | ✅ | Rust structural estimator |
| Dolo | ✅ | DSGE/macro modeling |
| Biogeme | ✅ | Discrete choice |
| torch-choice | ✅ | PyTorch discrete choice |
| jaxonometrics | ✅ | JAX econometrics |
| Argmin | ⚠️ | Rust optimizer - could be linear-programming |
| torchonometrics | ✅ | PyTorch econometrics |
| gegravity | ✅ | Gravity models |
| momentfit | ✅ | GMM fitting |
| PyLogit | ✅ | Discrete choice |
| upper-envelope | ✅ | Dynamic programming |
| OpenMx | ✅ | SEM |
| gEconpy | ✅ | DSGE Python |
| PyBLP | ✅ | BLP demand estimation |
| HARK | ✅ | Heterogeneous agents |
| **stargazer** | ❌ | **Should be pkg-visualization** - regression table output |
| appelpy | ✅ | Applied econometrics |
| pydsge | ✅ | DSGE Python |
| pynare | ✅ | Dynare-like Python |
| py-econometrics gmm | ✅ | GMM |
| econpizza | ✅ | NK models |
| gmm | ✅ | R GMM |
| ruspy | ✅ | Rust optimal stopping |
| XLogit | ✅ | Fast logit |
| QuantEcon.py | ✅ | Quantitative economics |
| lavaan | ✅ | SEM R |
| splm | ✅ | Spatial panels |

**Issues Found**:
- ❌ `stargazer` → should be `pkg-visualization` (it's a table formatting package, not estimation)

---

### 3. pkg-iv-rdd (IV & RDD Methods)
**Count**: 25 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| bunching | ✅ | Bunching estimation |
| causalweight | ✅ | Causal weights |
| pycinc | ✅ | Also DiD - OK to be in both |
| systemfit | ✅ | Systems of equations |
| ivreg | ✅ | IV regression |
| rddapp | ✅ | RDD Shiny app |
| rddensity | ✅ | RDD density tests |
| rdrobust | ✅ | Robust RDD |
| pyleebounds | ✅ | Lee bounds |
| ivmodel | ✅ | IV models |
| momentfit | ✅ | GMM - OK here too |
| rddtools | ✅ | RDD tools |
| AER | ✅ | Applied econometrics (has ivreg) |
| rdpower | ✅ | RDD power analysis |
| rdd | ✅ | RDD package |
| CausalImpact | ⚠️ | More DiD than IV, but OK |
| ATbounds | ✅ | Bounds estimation |
| py-econometrics gmm | ✅ | GMM |
| rdmulti | ✅ | Multiple cutoffs RDD |
| gmm | ✅ | R GMM |
| CausalPy | ✅ | Has RDD features |
| rdlocrand | ✅ | Local randomization RDD |
| ShiftShareSE | ✅ | Shift-share IV SEs |
| latenetwork | ✅ | LATE with networks |
| hdm | ✅ | High-dimensional methods including IV |

**Verdict**: ✅ All reasonable

---

### 4. pkg-pywhy-ecosystem (PyWhy & Causal Libraries)
**Count**: 23 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| pydoublelasso | ✅ | Double selection |
| DoubleML | ✅ | DML implementation |
| SynapseML | ✅ | Has DML |
| EconML | ✅ | Core PyWhy |
| PySensemakr | ✅ | Sensitivity analysis |
| CausalNLP | ✅ | Causal + NLP |
| scikit-uplift | ✅ | Uplift modeling |
| pydtr | ✅ | Dynamic treatment |
| CausalLift | ✅ | Uplift |
| pyhtelasso | ✅ | High-dim treatment effect |
| DoWhy | ✅ | Core PyWhy |
| CausalPlayground | ✅ | Educational |
| Doubly-Debiased-Lasso | ✅ | DML |
| CausalML | ✅ | Uber's causal ML |
| CausalLib | ✅ | IBM causal |
| causal-bert-pytorch | ✅ | BERT for causal |

**Verdict**: ✅ All correct

---

### 5. pkg-panel-data (Panel Data & Fixed Effects)
**Count**: 20 items | **Status**: ⚠️ One issue

| Package | Status | Notes |
|---------|--------|-------|
| plm | ✅ | Panel linear models |
| Greeners | ✅ | Has panel features |
| pydynpd | ✅ | Dynamic panels |
| PyFixest | ✅ | Python fixest |
| duckreg | ✅ | DuckDB regression |
| glmmTMB | ✅ | GLMM |
| nlme | ✅ | Nonlinear mixed effects |
| **collapse** | ❌ | **Should be pkg-data-manipulation** - it's a data.table alternative |
| FixedEffectModelPyHDFE | ✅ | High-dim FE |
| panelhetero | ✅ | Panel heterogeneity |
| Linearmodels | ✅ | Panel models |
| lme4 | ✅ | Mixed effects |
| fixest | ✅ | Fast fixed effects |
| FixedEffectModel | ✅ | FE models |
| bife | ✅ | Binary FE |
| alpaca | ✅ | FE APE |
| lfe | ✅ | Linear FE |
| panelr | ✅ | Panel regression |
| splm | ✅ | Spatial panels |
| clubSandwich | ✅ | Clustered SEs |

**Issues Found**:
- ❌ `collapse` → should be `pkg-data-manipulation` (it's primarily a fast data wrangling package)

---

### 6. pkg-causal-discovery (Causal Discovery & DAGs)
**Count**: 18 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| MCD | ✅ | Minimal causal discovery |
| bnlearn | ✅ | Bayesian network learning |
| dagitty | ✅ | DAG analysis |
| causal-llm-bfs | ✅ | LLM causal discovery |
| gCastle | ✅ | Huawei causal discovery |
| SDCI | ✅ | Structure discovery |
| ggdag | ✅ | DAG visualization |
| pcalg | ✅ | PC algorithm |
| Benchpress | ✅ | Causal discovery benchmark |
| LiNGAM | ✅ | Linear non-Gaussian |
| py-tetrad | ✅ | Python Tetrad |
| Tigramite | ✅ | Time series causal |
| CDT | ✅ | Causal discovery toolbox |
| CausalNex | ✅ | Bayesian networks |
| y0 | ✅ | Causal identification |
| DoWhy | ✅ | Has DAG features |
| causal-learn | ✅ | CMU causal discovery |
| Ananke | ✅ | Semiparametric causal |

**Verdict**: ✅ All correct

---

### 7. pkg-matching (Matching & Propensity Score)
**Count**: 15 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| matching | ✅ | Python matching |
| cobalt | ✅ | Covariate balance |
| matchingR | ✅ | R matching algorithms |
| algmatch | ✅ | Algorithm matching |
| ebal | ✅ | Entropy balancing |
| CBPS | ✅ | Covariate balancing PS |
| CausalMatch | ✅ | Causal matching |
| CausalGPS | ✅ | Continuous treatment GPS |
| WeightIt | ✅ | Weighting |
| fastmatch | ✅ | Fast matching |
| CausalInference | ✅ | General causal |
| gale-shapley | ⚠️ | Market design matching - could be game-theory |
| MatchIt | ✅ | Core R matching |
| optmatch | ✅ | Optimal matching |
| kep_solver | ⚠️ | Kidney exchange - could be game-theory |

**Notes**: gale-shapley and kep_solver are market design matching, could be game-theory but OK here

---

### 8. pkg-causal-forests (Causal Forests & CATE)
**Count**: 10 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| grf | ✅ | Generalized random forests |
| KECENI | ✅ | Network causal effects |
| EconML | ✅ | Has causal forests |
| CATENets | ✅ | CATE neural nets |
| mcf | ✅ | Modified causal forest |
| bartCause | ✅ | BART for causal |
| CausalML | ✅ | Uber's causal ML |
| causalToolbox | ✅ | R causal tools |
| DynTxRegime | ✅ | Dynamic treatment |
| DTRreg | ✅ | DTR regression |

**Verdict**: ✅ All correct

---

### 9. pkg-causal-mediation (Causal Mediation Analysis)
**Count**: 9 items | **Status**: ✅ Good

| Package | Status | Notes |
|---------|--------|-------|
| EValue | ✅ | Sensitivity E-value |
| causalweight | ✅ | Causal weights |
| CMAverse | ✅ | Causal mediation |
| mediation | ✅ | R mediation |
| PStrata | ✅ | Principal stratification |
| pyregadj | ✅ | Regression adjustment |
| spilled_t | ✅ | Spillover t-tests |
| ddml | ✅ | Double-debiased ML |
| sensemakr | ✅ | Sensitivity analysis |

**Verdict**: ✅ All correct

---

### 10. pkg-tmle (Targeted Learning)
**Count**: 5 items | **Status**: ⚠️ Missing SuperLearner!

| Package | Status | Notes |
|---------|--------|-------|
| ltmle | ✅ | Longitudinal TMLE |
| tmle | ✅ | R TMLE |
| tmle3 | ✅ | TMLE 3.0 |
| aipyw | ✅ | AIPW Python |
| causal-curve | ✅ | Continuous treatment |

**Issues Found**:
- ❌ **SuperLearner is MISSING** - it was assigned to pkg-automl which got filtered out (< 4 items)
- SuperLearner should be in this cluster - it's the foundational ensemble for TMLE

---

## EXPERIMENTATION (4 clusters)

### 11. pkg-power-simulation (Power Analysis & DOE)
**Count**: 12 items | **Status**: ✅ Good

All packages correctly assigned (pyDOE2, WebPower, Adaptive, Superpower, DoEgen, simChef, fabricatr, mlpwr, pwr, simr, ADOpy, DeclareDesign)

---

### 12. pkg-adaptive-bandits (Bandits & Adaptive Experiments)
**Count**: 9 items | **Status**: ✅ Good

All packages correctly assigned (contextual, Ax, ContextualBandits, BayesianBandits, MABWiser, OBP, abracadabra, PyXAB, SMPyBandits)

---

### 13. pkg-ab-testing (A/B Testing & Experiment Analysis)
**Count**: 9 items | **Status**: ✅ Good

All packages correctly assigned (randomizr, tea-tasting, cjoint, CausalMotifs, DeclareDesign, cregg, abracadabra, savvi, Ambrosia)

---

## MACHINE LEARNING (6 clusters)

### 14. pkg-nlp-llm (NLP & LLM Tools)
**Count**: 16 items | **Status**: ✅ Good

All packages correctly assigned (langgraph, text2vec, stm, tidytext, sentence-transformers, EDSL, Gensim, NLTK, anthropic, quanteda, openai, crewai, openai-agents, langchain, spaCy, Transformers)

---

### 15. pkg-gradient-boosting (Gradient Boosting)
**Count**: 15 items | **Status**: ✅ Good

All packages correctly assigned (MLForecast, xgboost, XGBoost, NGBoost, cuML, ranger, LightGBM, Linfa, CatBoost, glmnet, SmartCore, Scikit-learn Ens., SHAP)

---

### 16. pkg-recommender-systems (Recommender Systems)
**Count**: 7 items | **Status**: ✅ Good

All packages correctly assigned (Surprise, DeepCTR, LightFM, RecBole, recommenderlab, Implicit)

---

### 17. pkg-neural-networks (Deep Learning Frameworks)
**Count**: 6 items | **Status**: ✅ Good

All packages correctly assigned (JAX, DCA, scVI-tools, TensorFlow, PyTorch, VaDE)

---

### 18. pkg-time-series-ml (Deep Forecasting)
**Count**: 4 items | **Status**: ✅ Good

All packages correctly assigned (NeuralForecast, TS-Flint, PyKalman, sktime)

---

### 19. pkg-automl (AutoML & Hyperparameter Tuning)
**Count**: 0 items (FILTERED OUT) | **Status**: ❌ Problem!

**Packages that were assigned here but cluster was filtered**:
- SuperLearner → should be pkg-tmle
- tidymodels → could stay as "none" or move to gradient-boosting
- H2O Sparkling Water → could stay as "none" or move to gradient-boosting

**Action**: Move SuperLearner to pkg-tmle in CSV

---

## OPERATIONS RESEARCH (5 clusters)

### 20. pkg-simulation (Discrete Event Simulation)
**Count**: 23 items | **Status**: ✅ Good

All packages correctly assigned (SimPy, Ciw, Arena, RNetLogo, AnyLogic, CleanRL, Stable-Baselines3, nlrx, SuperSuit, ABIDES, NetLogoR, TorchRL, Mesa, OR-Gym, Simio, queueing, ABCE, pyNetLogo, RLlib, Gymnasium, MO-Gymnasium, simmer, AgentPy)

---

### 21. pkg-game-theory (Game Theory & Mechanism Design)
**Count**: 10 items | **Status**: ✅ Good

All packages correctly assigned (AuctionGym, OpenSpiel, deep-opt-auctions, pygambit, fairpyx, Nashpy, scarfmatch, PettingZoo, fairpy, AI Economist)

---

### 22. pkg-linear-programming (Linear & Integer Programming)
**Count**: 8 items | **Status**: ✅ Good

All packages correctly assigned (HiGHS, Faer, Pyomo, ortools, gurobipy, scipy.optimize)

---

### 23. pkg-convex-optimization (Convex Optimization)
**Count**: 1 item (FILTERED OUT) | **Status**: ⚠️

Only cvxpy was assigned - not enough for cluster.

---

### 24. pkg-routing (Routing & Logistics)
**Count**: 0-1 items | **Status**: ⚠️

Cluster exists but may not have enough items.

---

## TIME SERIES (3 clusters)

### 25. pkg-classical-forecasting (Classical Time Series)
**Count**: 19 items | **Status**: ✅ Good

All packages correctly assigned (urca, LocalProjections, pmdarima, fable, ARCH, Kats, vars, Augurs, KFAS, dlm, forecast, Metran, StatsForecast, tsDyn, dynlm, sktime, strucchange, mFilter, FilterPy)

---

### 26. pkg-prophet-style (Prophet & Trend Forecasting)
**Count**: 4 items | **Status**: ✅ Good

All packages correctly assigned (Prophet, prophet, Augurs)

---

### 27. pkg-hierarchical-forecasting
**Count**: 0 items (FILTERED OUT) | **Status**: ⚠️

No packages assigned - cluster empty.

---

## STATISTICS (8 clusters)

### 28. pkg-bayesian (Bayesian & Probabilistic Programming)
**Count**: 13 items | **Status**: ✅ Good

All packages correctly assigned (bayesplot, rstan, stochvol, Pyro, Bambi, blavaan, bsts, NumPyro, PyMC, PyMC Statespace, rstanarm, brms)

---

### 29. pkg-hypothesis-testing (Statistical Testing)
**Count**: 33 items | **Status**: ✅ Good

All packages correctly assigned - large cluster covering bootstrap, inference, standard errors, marginal effects, reporting.

---

### 30. pkg-survival-analysis (Survival Analysis)
**Count**: 12 items | **Status**: ✅ Good

All packages correctly assigned (mstate, pycox, lifelines, survminer, survHE, scikit-survival, survival, flexsurv)

---

### 31. pkg-synthetic-data (Synthetic Data Generation)
**Count**: 10 items | **Status**: ✅ Good

All packages correctly assigned (Synthpop, DataSynthesizer, CTGAN, Faker, DeepEcho, Gretel Synthetics, Mimesis, simPop, SDV, sdcMicro)

---

### 32. pkg-network-analysis (Network Analysis)
**Count**: 9 items | **Status**: ✅ Good

All packages correctly assigned (KECENI, ggraph, igraph, tidygraph, NetworkCausalTree, sna, Research Rabbit, python-louvain)

---

### 33. pkg-conformal (Conformal Prediction)
**Count**: 5 items | **Status**: ✅ Good

All packages correctly assigned (MAPIE, crepes, fortuna, TorchCP, puncc)

---

### 34. pkg-gams (GAMs & Flexible Regression)
**Count**: 2 items (in definitions) | **Status**: ⚠️

mgcv and gamlss assigned but may be filtered.

---

### 35. pkg-quantile-regression
**Count**: 3 items | **Status**: ⚠️

pyqreg, quantile-forest, pyrifreg assigned but may be filtered (< 4).

---

## INDUSTRY (9 clusters)

### 36. pkg-insurance (Insurance & Actuarial)
**Count**: 16 items | **Status**: ✅ Good

All packages correctly assigned (actuar, ChainLadder, OasisLMF, lifelines, pyliferisk, survminer, evd, extRemes, lifecontingencies, cplm, scikit-survival, chainladder-python, survival, Fairlearn, lifelib, flexsurv)

---

### 37. pkg-energy (Energy & Utilities)
**Count**: 15 items | **Status**: ✅ Good

All packages correctly assigned (eiapy, gridstatus, GenX, PowerModels.jl, PyPSA, catalystcoop-pudl, OpenDSS, pandapower)

---

### 38. pkg-marketing (Marketing & CLV)
**Count**: 14 items | **Status**: ✅ Good

All packages correctly assigned (PyMC Marketing, UpliftML, mmm_stan, pylift, MaMiMo, Robyn, BTYDplus, CLVTools, Lifetimes, LightweightMMM, ziln_cltv)

---

### 39. pkg-geospatial (Geospatial Analysis)
**Count**: 13 items | **Status**: ✅ Good

All packages correctly assigned (spacetrack, conflictcartographer, PySAL, Apache Sedona, Skyfield, sgp4, OSMnx, spdep, sf, tidytransit, spatialreg)

---

### 40. pkg-transportation (Transportation & Mobility)
**Count**: 12 items | **Status**: ✅ Good

All packages correctly assigned (Biogeme, PyLogit, xlogit, OSMnx, gtfs-kit, Apollo, mlogit, gmnl, mixl, tidytransit, SUMO, OpenTripPlanner)

---

### 41. pkg-sports (Sports Analytics)
**Count**: 10 items | **Status**: ✅ Good

All packages correctly assigned (nba_api, hockeyR, worldfootballR, nfl-data-py, Lahman, nflfastR, statsbombpy, mplsoccer, pybaseball, hoopR)

---

### 42. pkg-healthcare (Healthcare & Clinical)
**Count**: 8 items | **Status**: ✅ Good

All packages correctly assigned (mstate, BCEA, survHE, fhirclient, MONAI, hesim, scikit-survival, heemod)

---

### 43. pkg-finance (Quantitative Finance)
**Count**: 2 items | **Status**: ⚠️

FinRL, mbt_gym assigned but cluster may be filtered (< 4).

---

## DATA & UTILITIES (3 clusters)

### 44. pkg-data-manipulation (Data Wrangling)
**Count**: 5 items | **Status**: ⚠️ Missing collapse!

| Package | Status | Notes |
|---------|--------|-------|
| tidyverse | ✅ | R data science |
| Polars | ✅ | Fast dataframes |
| countrycode | ✅ | Country codes |
| data.table | ✅ | Fast R data |
| haven | ✅ | Read Stata/SPSS |

**Missing**: `collapse` should be here (currently in pkg-panel-data)

---

### 45. pkg-visualization (Data Visualization)
**Count**: 8 items | **Status**: ⚠️ Missing stargazer!

| Package | Status | Notes |
|---------|--------|-------|
| see | ✅ | easystats viz |
| conflictcartographer | ✅ | Conflict maps |
| tidyverse | ✅ | ggplot2 |
| cowplot | ✅ | ggplot extras |
| Connected Papers | ✅ | Paper viz |
| patchwork | ✅ | Combine plots |
| gt | ✅ | Tables |
| modelsummary | ✅ | Model tables |

**Missing**: `stargazer` should be here (currently in pkg-structural-estimation)

---

### 46. pkg-validation (Data Validation & Quality)
**Count**: 0 items (FILTERED OUT) | **Status**: ⚠️

No packages assigned to this cluster.

---

## Summary of Issues to Fix

### Critical Fixes (Wrong Cluster)

| Package | Current Cluster | Should Be | Reason |
|---------|----------------|-----------|--------|
| SuperLearner | pkg-automl (filtered) | **pkg-tmle** | Core TMLE ensemble method |
| collapse | pkg-panel-data | **pkg-data-manipulation** | Data.table alternative |
| stargazer | pkg-structural-estimation | **pkg-visualization** | Table formatting, not estimation |

### Minor Issues

| Package | Current | Notes |
|---------|---------|-------|
| inferference | none | Could be pkg-causal-mediation (interference) |
| linregress | none | Could be pkg-hypothesis-testing |
| Argmin | pkg-structural-estimation | Could also be pkg-linear-programming |

### Filtered Clusters (< 4 items)

| Cluster | Reason |
|---------|--------|
| pkg-automl | Only 3 packages (SuperLearner should move anyway) |
| pkg-convex-optimization | Only cvxpy |
| pkg-hierarchical-forecasting | No packages assigned |
| pkg-validation | No packages assigned |
| pkg-bayesian-ab | Possibly filtered |
| pkg-finance | Only 2 packages |

### Intentionally Unclustered Packages (none)

| Package | Reason |
|---------|--------|
| targets, rmarkdown, renv, here | R workflow tools |
| causaldata, wooldridge | Dataset packages |
| consensus, elicit | Web research tools |
| nvdlib | Cybersecurity niche |
| opentsne, factoranalyzer | No dim. reduction cluster |
| ndarray | Low-level Rust |

---

## Recommended CSV Changes

```
# Fix SuperLearner
superlearner,SuperLearner,Causal Inference (ML),R,pkg-tmle,,high,success

# Fix collapse
collapse,collapse,Data Workflow,R,pkg-data-manipulation,,high,success

# Fix stargazer
stargazer,stargazer,Regression Output,R,pkg-visualization,,high,success

# Fix inferference
inferference,inferference,Causal Inference (Interference),R,pkg-causal-mediation,,high,success

# Fix linregress
linregress,Linregress,Core Libraries & Linear Models,Rust,pkg-hypothesis-testing,,high,success
```
