"""Model M1: what kind of document is this? (TEXT_ML.md 4.3)

Word and character n-gram TF-IDF into a linear SVM, calibrated so the score reads as a probability.
Character n-grams cope with Hinglish spelling and typos.
"""

from typing import Any

from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC


def vectoriser() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, lowercase=True)),
    ])  # fmt: skip


class TypeModel:
    def __init__(self) -> None:
        self.pipe: Pipeline | None = None

    def fit(self, texts: list[str], labels: list[str]) -> "TypeModel":
        clf = CalibratedClassifierCV(LinearSVC(C=1.0, class_weight="balanced"), cv=3)
        self.pipe = Pipeline([("vec", vectoriser()), ("clf", clf)]).fit(texts, labels)
        return self

    def predict(self, text: str) -> dict[str, Any]:
        assert self.pipe is not None, "the type model is not trained"
        probs = self.pipe.predict_proba([text])[0]
        order = probs.argsort()[::-1]
        classes = self.pipe.classes_
        return {"doc_type": str(classes[order[0]]), "confidence": float(probs[order[0]]),
                "alternatives": [{"doc_type": str(classes[i]), "confidence": float(probs[i])} for i in order[1:3]]}  # fmt: skip

    def predict_many(self, texts: list[str]) -> list[str]:
        assert self.pipe is not None
        return [str(x) for x in self.pipe.predict(texts)]
