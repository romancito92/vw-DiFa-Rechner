from config import RATE_TABLE

def get_distance_class(km):
    """Ordnet die Distanzklasse gemäß MVP-Regeln zu."""
    if km < 100:
        return "kurz"
    if km <= 250:
        return "mittel"
    return "lang"


def calculate_case_a(km, one_way_minutes, a1_extra_per_km=0.0):
    """Berechnet dynamische Unter-/Obergrenze, Mittelwert und Gesamtminuten f?r Fall A."""
    price_a1_base = 29 + (1.30 * km)
    fuel_surcharge_total = a1_extra_per_km * km
    price_a1 = price_a1_base + fuel_surcharge_total
    total_minutes = (2 * one_way_minutes) + 30
    price_a2 = (total_minutes / 60) * 60

    lower_price = min(price_a1, price_a2)
    upper_price = max(price_a1, price_a2)
    price_mid = (lower_price + upper_price) / 2

    return (
        lower_price,
        price_mid,
        upper_price,
        total_minutes,
        price_a1,
        price_a2,
        price_a1_base,
        fuel_surcharge_total,
    )


def calculate_case_b_ek(ek_price):
    """Berechnet die drei EK-basierten Verkaufspreise für Fall B.1."""
    return {
        "EK x 1,3": ek_price * 1.3,
        "EK x 1,4": ek_price * 1.4,
        "EK x 1,5": ek_price * 1.5,
    }


def calculate_case_b_table(km, vehicle_type):
    """Berechnet Distanzklasse, Satzwerte und Preise für Fall B.2."""
    distance_class = get_distance_class(km)
    rates = RATE_TABLE[vehicle_type][distance_class]
    prices = {
        "Tabellen-Min": km * rates["min"],
        "Tabellen-Mittel": km * rates["mittel"],
        "Tabellen-Max": km * rates["max"],
    }
    return distance_class, rates, prices


