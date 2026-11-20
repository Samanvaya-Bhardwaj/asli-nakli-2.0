"""City coordinates and great-circle distance, for the scan-spread rule (PLAN.md 12.2)."""

from math import asin, cos, radians, sin, sqrt

CITIES: dict[str, tuple[float, float]] = {
    "Delhi": (28.6139, 77.2090), "Mumbai": (19.0760, 72.8777), "Bengaluru": (12.9716, 77.5946),
    "Pune": (18.5204, 73.8567), "Hyderabad": (17.3850, 78.4867), "Baddi": (30.9578, 76.7914),
    "Chennai": (13.0827, 80.2707), "Kolkata": (22.5726, 88.3639), "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873), "Lucknow": (26.8467, 80.9462), "Chandigarh": (30.7333, 76.7794),
    "Kochi": (9.9312, 76.2673), "Patna": (25.5941, 85.1376), "Nagpur": (21.1458, 79.0882),
    "Thane": (19.2183, 72.9781), "Gurugram": (28.4595, 77.0266), "Noida": (28.5355, 77.3910),
}  # fmt: skip

CITY_STATE: dict[str, str] = {
    "Delhi": "DL", "Mumbai": "MH", "Bengaluru": "KA", "Pune": "MH", "Hyderabad": "TG", "Baddi": "HP", "Chennai": "TN",
    "Kolkata": "WB", "Ahmedabad": "GJ", "Jaipur": "RJ", "Lucknow": "UP", "Chandigarh": "CH", "Kochi": "KL", "Patna": "BR",
    "Nagpur": "MH", "Thane": "MH", "Gurugram": "HR", "Noida": "UP",
}  # fmt: skip


def distance_km(a: str, b: str) -> float:
    """Haversine distance. Raises KeyError for a city that is not in the table; callers decide what that means."""
    (lat1, lon1), (lat2, lon2) = CITIES[a], CITIES[b]
    p1, p2 = radians(lat1), radians(lat2)
    h = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))
