import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_api_types


def test_the_schema_on_disk_is_the_one_the_python_models_produce():
    on_disk = gen_api_types.TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert on_disk == gen_api_types.build(), "run infra/scripts/gen_api_types.py and npm run gen:types"
