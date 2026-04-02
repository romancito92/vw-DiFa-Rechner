from __future__ import annotations

import direktfahrt_rechner as app
from tankerkoenig_helpers import build_diesel_price_average


def base_ctx(**overrides):
    ctx = {
        "pickup_area": "A",
        "shipment_count": 1,
        "is_late_registration": False,
        "is_late_pickup": False,
        "pickup_window": "17:00-18:00",
        "additional_shipments": 0,
        "self_dropoff_after_19": False,
    }
    ctx.update(overrides)
    return ctx


def piece(weight, length=40.0, width=30.0, height=20.0):
    return {
        "weight_kg": float(weight),
        "length_cm": float(length),
        "width_cm": float(width),
        "height_cm": float(height),
    }


def run_tests():
    cfg = app.load_parcel_config()

    # 1) Summiertes Grundgewicht (2x4kg => 8kg => EXP 49 EUR)
    res = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [piece(4), piece(4)],
        [],
        "standard",
        0.0,
        [],
        base_ctx(),
        insurance_enabled=False,
    )
    assert res is not None
    assert round(res["base_total"], 2) == 49.00

    # 2) LZ48 Maximalgewicht je Einzelpackstück (50kg)
    lz48_reasons = app.evaluate_carrier_eligibility(cfg, "LZ48", [piece(55)], [])
    assert any("> 50.0 kg" in r for r in lz48_reasons)

    # 3) Spätabholung ohne Spätanmeldung
    res = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [piece(4)],
        [],
        "standard",
        0.0,
        [],
        base_ctx(is_late_pickup=True, pickup_window="18:00-19:00"),
        insurance_enabled=False,
    )
    assert round(res["late_fee"], 2) == 0.00
    assert round(res["late_pickup_fee"], 2) == 25.00

    # 4) Spätanmeldung ohne Spätabholung
    res = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [piece(4)],
        [],
        "standard",
        0.0,
        [],
        base_ctx(is_late_registration=True, is_late_pickup=False),
        insurance_enabled=False,
    )
    assert round(res["late_fee"], 2) == 25.00
    assert round(res["late_pickup_fee"], 2) == 0.00

    # 5) Höherversicherung: nur wenn aktiviert und >250
    res_off = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [piece(4)],
        [],
        "standard",
        1000.0,
        [],
        base_ctx(),
        insurance_enabled=False,
    )
    res_on = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [piece(4)],
        [],
        "standard",
        1000.0,
        [],
        base_ctx(),
        insurance_enabled=True,
    )
    assert round(res_off["insurance_fee"], 2) == 0.00
    assert round(res_on["insurance_fee"], 2) == 1.50

    # 6) EXP Samstagszustellung = +25, nicht auf LZ48
    res_exp_base = app.calculate_case_c_tariff(
        cfg, "EXP", [piece(4)], [], "standard", 0.0, [], base_ctx(), False
    )
    res_exp_sat = app.calculate_case_c_tariff(
        cfg, "EXP", [piece(4)], [], "standard", 0.0, ["saturday_exp"], base_ctx(), False
    )
    res_lz_base = app.calculate_case_c_tariff(
        cfg, "LZ48", [piece(4)], [], "standard", 0.0, [], base_ctx(), False
    )
    res_lz_sat = app.calculate_case_c_tariff(
        cfg, "LZ48", [piece(4)], [], "standard", 0.0, ["saturday_exp"], base_ctx(), False
    )
    assert round(res_exp_sat["total"] - res_exp_base["total"], 2) == 25.00
    assert round(res_lz_sat["total"] - res_lz_base["total"], 2) == 0.00

    # 7) Überlänge 280-309: 1. PS 45, weitere je 15
    res_len_1 = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [piece(4, length=281, width=10, height=10)],
        [],
        "standard",
        0.0,
        [],
        base_ctx(),
        False,
    )
    res_len_3 = app.calculate_case_c_tariff(
        cfg,
        "EXP",
        [
            piece(4, length=281, width=10, height=10),
            piece(4, length=282, width=10, height=10),
            piece(4, length=283, width=10, height=10),
        ],
        [],
        "standard",
        0.0,
        [],
        base_ctx(),
        False,
    )
    over1 = [a for l, a in res_len_1["carrier_surcharge_breakdown"] if "Überlänge" in l][0]
    over3 = [a for l, a in res_len_3["carrier_surcharge_breakdown"] if "Überlänge" in l][0]
    assert round(over1, 2) == 45.00
    assert round(over3, 2) == 75.00

    # 8) Tankerkoenig-Mittelwert nutzt offene Stationen, wenn vorhanden
    summary = build_diesel_price_average(
        [
            {"name": "A", "isOpen": False, "price": 1.599, "dist": 0.3},
            {"name": "B", "isOpen": True, "price": 1.629, "dist": 0.1},
            {"name": "C", "isOpen": True, "price": 1.589, "dist": 1.2},
        ]
    )
    assert round(summary["price"], 3) == 1.609
    assert summary["station_count"] == 2
    assert summary["open_station_count"] == 2

    # 9) Fallback auf `diesel`, falls keine `price`-Spalte vorhanden ist
    summary = build_diesel_price_average(
        [
            {"name": "D", "isOpen": True, "diesel": 1.709, "dist": 0.8},
            {"name": "E", "isOpen": True, "diesel": 1.699, "dist": 1.1},
        ]
    )
    assert round(summary["price"], 3) == 1.704

    # 10) A-Fall ohne Hebebuehne bleibt bei Basis 29 und 1,30 EUR/km
    result = app.calculate_case_a(92, 72, 0.0, False)
    assert round(result[4], 2) == 148.60
    assert round(result[5], 2) == 174.00
    assert round(result[8], 2) == 29.00
    assert round(result[9], 2) == 1.30
    assert round(result[10], 2) == 1.00

    # 11) A-Fall mit Hebebuehne: A.1 +0,15 EUR/km und +10 EUR Basis, A.2 +20 %
    result = app.calculate_case_a(92, 72, 0.0, True)
    assert round(result[4], 2) == 172.40
    assert round(result[5], 2) == 208.80
    assert round(result[8], 2) == 39.00
    assert round(result[9], 2) == 1.45
    assert round(result[10], 2) == 1.20

    # 12) Finale Angebotsrundung: immer auf die naechste ungerade ganze Zahl nach unten
    assert app.round_down_to_odd_price(58.90) == 57
    assert app.round_down_to_odd_price(57.90) == 57
    assert app.round_down_to_odd_price(56.00) == 55
    assert app.round_down_to_odd_price(55.20) == 55

    # 13) B-Fall EK-Multiplikatoren nutzen dieselbe finale Rundungsregel
    ek_prices = app.calculate_case_b_ek(200.0)
    assert ek_prices["EK x 1,3"] == 259
    assert ek_prices["EK x 1,4"] == 279
    assert ek_prices["EK x 1,5"] == 299

    # 14) Packstück-Metrik sortiert Seiten korrekt und berechnet Gurtmaß aus der längsten Seite
    piece_metrics = app.get_piece_metrics(cfg, piece(4, length=20, width=80, height=150))
    assert round(piece_metrics["longest_side_cm"], 1) == 150.0
    assert round(piece_metrics["second_longest_side_cm"], 1) == 80.0
    assert round(piece_metrics["girth_plus_length"], 1) == 350.0

    # 15) LZ48/UPS: längste Seite >274 oder Gurtmaß >300 schließen aus, auch wenn Länge-Feld selbst klein ist
    lz48_longest_side_reasons = app.evaluate_carrier_eligibility(
        cfg, "LZ48", [piece(4, length=40, width=275, height=20)], []
    )
    assert any("274.0 cm" in r for r in lz48_longest_side_reasons)

    lz48_girth_reasons = app.evaluate_carrier_eligibility(
        cfg, "LZ48", [piece(4, length=20, width=80, height=150)], []
    )
    assert any("> 300.0 cm" in r for r in lz48_girth_reasons)

    # 16) LZ48/UPS: 30 EUR Zuschlag pro Packstück bei längster Seite >100 oder zweitlängster Seite >76
    lz48_dim_surcharge_1 = app.calculate_case_c_tariff(
        cfg,
        "LZ48",
        [piece(4, length=101, width=30, height=20)],
        [],
        "standard",
        0.0,
        [],
        base_ctx(),
        False,
    )
    assert any(
        "100/76" in label and round(amount, 2) == 30.00
        for label, amount in lz48_dim_surcharge_1["carrier_surcharge_breakdown"]
    )

    lz48_dim_surcharge_2 = app.calculate_case_c_tariff(
        cfg,
        "LZ48",
        [piece(4, length=90, width=77, height=20)],
        [],
        "standard",
        0.0,
        [],
        base_ctx(),
        False,
    )
    assert any(
        "100/76" in label and round(amount, 2) == 30.00
        for label, amount in lz48_dim_surcharge_2["carrier_surcharge_breakdown"]
    )

    print("OK: Alle Preislogik-Regressionstests bestanden.")


if __name__ == "__main__":
    run_tests()
