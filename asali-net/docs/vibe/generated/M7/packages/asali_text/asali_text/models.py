"""Saving and loading the trained models with the version and training data they came from."""

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import sklearn

from asali_text.classify_issue import IssueModel
from asali_text.classify_type import TypeModel
from asali_text.ranker import LinkModel


@dataclass
class Models:
    type: TypeModel
    issue: IssueModel
    link: LinkModel
    meta: dict[str, object]


def save_models(models: Models, out: Path, data_hash: str, extra: dict[str, object] | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(models.type, out / "type.joblib", compress=3)
    joblib.dump(models.issue, out / "issue.joblib", compress=3)
    joblib.dump(models.link, out / "link.joblib", compress=3)
    meta = {"sklearn": sklearn.__version__, "data_hash": data_hash, **(extra or {})}
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def load_models(path: Path) -> Models:
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    if meta["sklearn"] != sklearn.__version__:
        raise RuntimeError(f"models were trained with scikit-learn {meta['sklearn']}, this is {sklearn.__version__}; retrain")
    return Models(joblib.load(path / "type.joblib"), joblib.load(path / "issue.joblib"), joblib.load(path / "link.joblib"), meta)
