"""Sample-weight derivation for the ranking model.

Implements Ra1 from the May 2026 audit (book §8.3.2 / YouTube watch-time
weighting). Positive examples are scaled by `1 + log1p(engagement)` so
that a 5-minute deeply-engaged session contributes more to training
than a 3-second click. Negative examples (no engagement) keep weight
1.0, preserving class balance.

Inputs:
    y_engagement: 1-D numpy array of continuous engagement scores
        (already weighted by the existing per-signal weights in
        scripts/rank_all_content.py — clicks * 5 + dwell_min * 1 + …).
        y_engagement[i] == 0 means "no observed engagement".

Outputs:
    weights: 1-D numpy array, same shape as input, same dtype float64.
        weights[i] >= 1.0 always.

Side effects:
    None.

Reproducibility:
    Pure function. Same input → same output.
"""

from __future__ import annotations

import numpy as np


def compute_sample_weights(y_engagement: np.ndarray) -> np.ndarray:
    """Return per-sample weights for LightGBM-style training.

    Positive samples get ``1.0 + log1p(y)`` (so y == 1 → weight ~1.69,
    y == 10 → ~3.40, y == 100 → ~5.62). Negatives stay at 1.0.

    Why ``1 + log1p`` and not just ``log1p``: log1p(0) == 0, which would
    eliminate the negative class from training entirely. We need the
    negatives at unit weight so the classifier still learns "what's
    boring".
    """
    y = np.asarray(y_engagement, dtype=np.float64)
    if y.size == 0:
        return np.empty(0, dtype=np.float64)
    if np.any(y < 0):
        # The score formula in rank_all_content.py clamps to >= 0 before
        # this function ever sees a value, so negatives here mean we got
        # called from somewhere new. Fail loud per architecture rule E14
        # ("no silent failure").
        raise ValueError(
            "compute_sample_weights: negative engagement scores are not "
            "allowed (got min={:.4f}). Clamp the score to >= 0 upstream.".format(
                float(np.min(y))
            )
        )
    return np.where(y > 0, 1.0 + np.log1p(y), 1.0).astype(np.float64)


__all__ = ["compute_sample_weights"]
