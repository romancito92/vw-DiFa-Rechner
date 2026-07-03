from config import RATE_TABLE
from pricing_config import load_pricing_config, validate_pricing_config


def round_down_to_odd_price(value):
    """Round a final quote down to the next odd whole number."""
    if value <= 0:
        return 0
    rounded = int(value)
    if rounded % 2 == 0:
        rounded -= 1
    return max(0, rounded)


def get_distance_class(km):
    """Ordnet die Distanzklasse gemäß MVP-Regeln zu."""
    if km < 100:
        return "kurz"
    if km <= 250:
        return "mittel"
    return "lang"


def calculate_case_a(
    km,
    one_way_minutes,
    a1_extra_per_km=0.0,
    liftgate_required=False,
    pricing_config=None,
):
    """Berechnet dynamische Unter-/Obergrenze, Mittelwert und Gesamtminuten für Fall A."""
    if pricing_config is None:
        pricing_config = load_pricing_config()
    validate_pricing_config(pricing_config)
    vehicle_key = "transporter_liftgate" if liftgate_required else "transporter"
    vehicle_pricing = pricing_config["modes"]["A"]["vehicles"][vehicle_key]
    a1_base_fee = float(vehicle_pricing["base_price_eur"])
    a1_rate_per_km = float(vehicle_pricing["km_price_eur"])
    a2_multiplier = 1.20 if liftgate_required else 1.00

    price_a1_base = a1_base_fee + (a1_rate_per_km * km)
    fuel_surcharge_total = a1_extra_per_km * km
    price_a1 = price_a1_base + fuel_surcharge_total
    total_minutes = (2 * one_way_minutes) + 30
    price_a2 = ((total_minutes / 60) * 60) * a2_multiplier

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
        a1_base_fee,
        a1_rate_per_km,
        a2_multiplier,
    )


def build_case_a_preview(
    pricing_config,
    km=92,
    one_way_minutes=72,
    liftgate_required=False,
):
    """Build an admin preview using the exact Mode A calculation and rounding rules."""
    (
        lower_price,
        price_mid,
        upper_price,
        _,
        price_a1,
        price_a2,
        _,
        _,
        _,
        _,
        _,
    ) = calculate_case_a(
        km,
        one_way_minutes,
        a1_extra_per_km=0.0,
        liftgate_required=liftgate_required,
        pricing_config=pricing_config,
    )
    return {
        "price_a1_raw": price_a1,
        "price_a1_rounded": round_down_to_odd_price(price_a1),
        "price_a2_rounded": round_down_to_odd_price(price_a2),
        "lower_rounded": round_down_to_odd_price(lower_price),
        "mid_rounded": round_down_to_odd_price(price_mid),
        "upper_rounded": round_down_to_odd_price(upper_price),
    }


def calculate_case_b_ek(ek_price):
    """Berechnet die drei EK-basierten Verkaufspreise für Fall B.1."""
    return {
        "EK x 1,3": round_down_to_odd_price(ek_price * 1.3),
        "EK x 1,4": round_down_to_odd_price(ek_price * 1.4),
        "EK x 1,5": round_down_to_odd_price(ek_price * 1.5),
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
