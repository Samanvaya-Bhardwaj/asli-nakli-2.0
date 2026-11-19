"""The names mentions are matched against: products, organisations, cities (TEXT_ML.md 4.4)."""

from dataclasses import dataclass, field

CITY_VARIANTS: dict[str, str] = {
    "delhi": "Delhi", "new delhi": "Delhi", "mumbai": "Mumbai", "bombay": "Mumbai", "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru", "pune": "Pune", "hyderabad": "Hyderabad", "baddi": "Baddi", "chennai": "Chennai",
    "madras": "Chennai", "kolkata": "Kolkata", "calcutta": "Kolkata", "ahmedabad": "Ahmedabad", "jaipur": "Jaipur",
    "lucknow": "Lucknow", "chandigarh": "Chandigarh", "kochi": "Kochi", "cochin": "Kochi", "patna": "Patna",
    "nagpur": "Nagpur", "thane": "Thane", "gurugram": "Gurugram", "gurgaon": "Gurugram", "noida": "Noida",
}  # fmt: skip


@dataclass(frozen=True)
class ProductName:
    gtin: str
    brand: str
    generic: str
    strength: str


@dataclass(frozen=True)
class Gazetteer:
    products: tuple[ProductName, ...] = ()
    orgs: dict[str, str] = field(default_factory=dict)  # org id -> name
    issuers: tuple[str, ...] = ("TP", "MV", "KS")

    def org_forms(self) -> list[tuple[str, str]]:
        """(form to look for, org id): the full name and a short form of its first two words."""
        out = []
        for org_id, name in self.orgs.items():
            out.append((name.lower(), org_id))
            words = name.lower().split()
            if len(words) > 2:
                out.append((" ".join(words[:2]), org_id))
        return out
