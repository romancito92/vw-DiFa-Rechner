from __future__ import annotations

import direktfahrt_rechner as app


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

    print("OK: Alle Preislogik-Regressionstests bestanden.")


if __name__ == "__main__":
    run_tests()
