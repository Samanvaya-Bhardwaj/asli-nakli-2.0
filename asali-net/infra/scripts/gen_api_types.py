"""Write the JSON Schema of the portal's API shapes (services/node/asali_node/contract.py) for the TypeScript generator.

    python infra/scripts/gen_api_types.py            # writes apps/portal-web/src/api/contract.schema.json
    python infra/scripts/gen_api_types.py --check    # exits 1 if the file on disk is out of date

`npm run gen:types` in apps/portal-web (run after this script) turns the schema into src/api/generated.ts.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "node"))
from asali_node.contract import EXPORTS

TARGET = ROOT / "apps" / "portal-web" / "src" / "api" / "contract.schema.json"


def untitle(node: object) -> None:
    """Pydantic titles every field; the generator would turn each into a type alias, so drop them."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for prop in value.values():
                    if isinstance(prop, dict):
                        prop.pop("title", None)
            untitle(value)
    elif isinstance(node, list):
        for item in node:
            untitle(item)


def build() -> str:
    defs: dict[str, object] = {}
    for name, model in EXPORTS.items():
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        defs.update(schema.pop("$defs", {}))
        schema["title"] = name
        defs[name] = schema
    root = {"$schema": "http://json-schema.org/draft-07/schema#", "title": "Contract", "type": "object",
            "properties": {n: {"$ref": f"#/$defs/{n}"} for n in EXPORTS}, "required": list(EXPORTS),
            "additionalProperties": False, "$defs": defs}  # fmt: skip
    untitle(root)
    return json.dumps(root, indent=1, sort_keys=True) + "\n"


def main() -> int:
    text = build()
    if "--check" in sys.argv:
        ok = TARGET.exists() and TARGET.read_text(encoding="utf-8").replace("\r\n", "\n") == text
        print(
            "api schema up to date" if ok else "api schema is out of date: run infra/scripts/gen_api_types.py"
        )
        return 0 if ok else 1
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
