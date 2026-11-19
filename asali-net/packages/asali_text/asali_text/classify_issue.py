"""Model M2: what is a complaint about? Several labels can apply (TEXT_ML.md 4.7)."""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

from asali_text.classify_type import vectoriser

LABELS = ["suspected_fake", "packaging_different", "no_effect", "side_effect", "expired_or_near_expiry", "overcharged",
          "damaged_pack", "wrong_medicine", "other"]  # fmt: skip


class IssueModel:
    def __init__(self) -> None:
        self.pipe: Pipeline | None = None
        self.mlb = MultiLabelBinarizer(classes=LABELS)
        self.thresholds: np.ndarray = np.full(len(LABELS), 0.5)

    def fit(
        self, texts: list[str], labels: list[list[str]], val_texts: list[str], val_labels: list[list[str]]
    ) -> "IssueModel":
        y = self.mlb.fit_transform(labels)
        clf = OneVsRestClassifier(
            LogisticRegression(C=5.0, class_weight="balanced", max_iter=1000)
        )  # C chosen on the validation split
        self.pipe = Pipeline([("vec", vectoriser()), ("clf", clf)]).fit(texts, y)
        self._tune(val_texts, self.mlb.transform(val_labels))
        return self

    def _tune(self, texts: list[str], y: np.ndarray) -> None:
        """Pick each label's threshold on the validation split to maximise its F1, then freeze it."""
        assert self.pipe is not None
        probs = self.pipe.predict_proba(texts)
        for j in range(len(LABELS)):
            best, best_f1 = 0.5, -1.0
            for t in np.arange(0.2, 0.81, 0.05):
                pred = probs[:, j] >= t
                tp = float((pred & (y[:, j] == 1)).sum())
                f1 = 2 * tp / max(1.0, float(pred.sum() + y[:, j].sum()))
                if f1 > best_f1:
                    best, best_f1 = float(t), f1
            self.thresholds[j] = best

    def predict(self, text: str) -> list[str]:
        assert self.pipe is not None, "the issue model is not trained"
        p = self.pipe.predict_proba([text])[0]
        labels = [LABELS[j] for j in range(len(LABELS)) if p[j] >= self.thresholds[j]]
        return labels or ["other"]

    def predict_matrix(self, texts: list[str]) -> np.ndarray:
        assert self.pipe is not None
        return (self.pipe.predict_proba(texts) >= self.thresholds).astype(int)
