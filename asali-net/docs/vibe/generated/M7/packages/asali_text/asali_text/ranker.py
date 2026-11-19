"""Model M3: how likely is it that this document is about this record? (TEXT_ML.md 4.5)

A scaled logistic regression over the link features, calibrated on the validation split so the output
can be read as a probability. Thresholds: 0.8 linked, 0.6 possible, below that dropped.
"""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class LinkModel:
    def __init__(self) -> None:
        self.base: Pipeline | None = None
        self.calibrated: CalibratedClassifierCV | None = None

    def fit(self, x: np.ndarray, y: np.ndarray, val_x: np.ndarray, val_y: np.ndarray) -> "LinkModel":
        self.base = Pipeline([("scale", StandardScaler()), ("lr", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000))]).fit(x, y)
        self.calibrated = CalibratedClassifierCV(FrozenEstimator(self.base), method="sigmoid").fit(val_x, val_y)
        return self

    def proba(self, x: np.ndarray) -> np.ndarray:
        assert self.calibrated is not None, "the link model is not trained"
        return np.asarray(self.calibrated.predict_proba(x)[:, 1]) if len(x) else np.zeros(0)

    def contributions(self, row: np.ndarray) -> np.ndarray:
        """Coefficient times scaled value, per feature: what pushed this link up or down."""
        assert self.base is not None
        scaled = self.base.named_steps["scale"].transform([row])[0]
        return np.asarray(self.base.named_steps["lr"].coef_[0] * scaled)
