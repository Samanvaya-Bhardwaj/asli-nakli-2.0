from pathlib import Path

import pytest
from snapshot import SnapshotError, snapshot


def make(base: Path, rel: str, text: str) -> Path:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_copies_file_under_milestone_keeping_relative_path(tmp_path: Path) -> None:
    src = make(tmp_path, "packages/a/b.py", "x = 1\n")
    written = snapshot("M1", [src], base=tmp_path)
    target = tmp_path / "docs/vibe/generated/M1/packages/a/b.py"
    assert written == [target]
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_refuses_to_overwrite_existing_snapshot(tmp_path: Path) -> None:
    src = make(tmp_path, "a.py", "first\n")
    snapshot("M1", [src], base=tmp_path)
    src.write_text("second\n", encoding="utf-8")
    with pytest.raises(SnapshotError, match="already snapshotted"):
        snapshot("M1", [src], base=tmp_path)
    assert (tmp_path / "docs/vibe/generated/M1/a.py").read_text(encoding="utf-8") == "first\n"


def test_refuses_files_outside_base(tmp_path: Path) -> None:
    outside = make(tmp_path.parent, "outside_snapshot_test.py", "y\n")
    with pytest.raises(SnapshotError, match="outside"):
        snapshot("M1", [outside], base=tmp_path)


def test_refuses_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError, match="does not exist"):
        snapshot("M1", [tmp_path / "nope.py"], base=tmp_path)
