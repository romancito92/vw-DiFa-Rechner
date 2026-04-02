import json
from config import PARCEL_CONFIG_PATH

UPS_LONGEST_SIDE_SURCHARGE_THRESHOLD_CM = 100.0
UPS_SECOND_LONGEST_SIDE_SURCHARGE_THRESHOLD_CM = 76.0
UPS_DIMENSION_SURCHARGE_EUR_PER_PIECE = 30.0

def load_parcel_config():
    """Laedt externe Tarifkonfiguration für Modus C."""
    with PARCEL_CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_weight_price(weight_kg, tariff_rows):
    """Liefert Grundpreis je Paket für das passende Gewichtsband."""
    for row in tariff_rows:
        if weight_kg <= float(row["max_weight_kg"]):
            return float(row["price_eur"]), float(row["max_weight_kg"])
    return None, None


def get_piece_dimensions(piece):
    """Sortiert PackstÃ¼ckmaÃŸe absteigend in lÃ¤ngste, zweitlÃ¤ngste und kÃ¼rzeste Seite."""
    dims = sorted(
        [
            float(piece["length_cm"]),
            float(piece["width_cm"]),
            float(piece["height_cm"]),
        ],
        reverse=True,
    )
    return dims[0], dims[1], dims[2]


def get_piece_metrics(cfg, piece):
    """Berechnet Real-/Volumen-/Abrechnungsgewicht und Gurtmaß je Packstück."""
    real_weight = float(piece["weight_kg"])
    longest_side, second_longest_side, shortest_side = get_piece_dimensions(piece)
    volume_weight = (
        float(piece["length_cm"]) * float(piece["width_cm"]) * float(piece["height_cm"])
    ) / float(cfg["calculation_rules"]["volumetric_divisor_cm3_per_kg"])
    if cfg["calculation_rules"]["use_higher_of_real_and_volumetric_weight"]:
        billable_weight = max(real_weight, volume_weight)
    else:
        billable_weight = real_weight
    girth_plus_length = longest_side + 2 * second_longest_side + 2 * shortest_side
    return {
        "real_weight": real_weight,
        "volume_weight": volume_weight,
        "billable_weight": billable_weight,
        "longest_side_cm": longest_side,
        "second_longest_side_cm": second_longest_side,
        "shortest_side_cm": shortest_side,
        "girth_plus_length": girth_plus_length,
    }


def normalize_postal_code(value):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:5]


def postal_matches_patterns(postal_code, patterns):
    if not postal_code or len(postal_code) < 5:
        return False
    postal_int = int(postal_code)

    for prefix in patterns.get("prefix_x", []):
        if postal_code.startswith(str(prefix)):
            return True
    for start, end in patterns.get("ranges", []):
        if int(start) <= postal_int <= int(end):
            return True
    for exact in patterns.get("exact", []):
        if postal_int == int(exact):
            return True
    return False


def determine_pickup_area(cfg, pickup_postal_code):
    rules = cfg.get("pickup_area_rules", {})
    plz = normalize_postal_code(pickup_postal_code)
    if len(plz) != 5:
        return None
    if postal_matches_patterns(plz, rules.get("A", {}).get("postal_patterns", {})):
        return "A"
    if postal_matches_patterns(plz, rules.get("B", {}).get("postal_patterns", {})):
        return "B"
    return "C"


def evaluate_shipment_eligibility(cfg, country_code, pieces, is_pallet, is_non_parcel):
    """Globale Pruefung für Modus C (unabhaengig vom Carrier)."""
    rules = cfg["validation_rules"]
    blocking = []
    warnings = []

    if country_code not in rules["allowed_destination_countries"]:
        blocking.append("Nur innerdeutsche Sendungen (DE) sind in Modus C erlaubt.")
    if is_pallet:
        warnings.append(
            "Palettensendung erkannt: LZ48 ist ausgeschlossen, EXP bitte mit DeKu-Station abstimmen."
        )
    if is_non_parcel:
        blocking.append("Nicht pakettaugliche Sendung - bitte anderen Transportmodus nutzen.")

    max_weight = float(rules["max_weight_kg"])
    for idx, piece in enumerate(pieces, start=1):
        metrics = get_piece_metrics(cfg, piece)
        if metrics["billable_weight"] > max_weight:
            blocking.append(
                f"Packstück {idx}: Abrechnungsgewicht {metrics['billable_weight']:.1f} kg über globalem Limit {max_weight:.1f} kg."
            )
    return blocking, warnings


def evaluate_carrier_eligibility(cfg, tariff_code, pieces, selected_exp_services=None):
    """Carrier-spezifische Dealbreaker, bereits ein einzelnes Packstück kann ausschliessen."""
    rules = cfg["carrier_validation_rules"][tariff_code]
    reasons = []
    max_weight = float(rules["max_weight_kg"])
    max_length = float(rules["max_length_cm"])
    max_lu = float(rules["max_girth_plus_length_cm"])

    for idx, piece in enumerate(pieces, start=1):
        metrics = get_piece_metrics(cfg, piece)
        lu = metrics["girth_plus_length"]
        longest_side = metrics["longest_side_cm"]
        if metrics["billable_weight"] > max_weight:
            reasons.append(
                f"Packstück {idx}: Abrechnungsgewicht {metrics['billable_weight']:.1f} kg > {max_weight:.1f} kg"
            )
        if False and longest_side > max_length:
            reasons.append(
                f"Packstück {idx}: Länge {piece['length_cm']:.1f} cm > {max_length:.1f} cm"
            )
        if longest_side > max_length:
            reasons.append(
                f"Packstück {idx}: Längste Seite {longest_side:.1f} cm > {max_length:.1f} cm"
            )
        if lu > max_lu:
            reasons.append(
                f"Packstück {idx}: Länge+Umfang {lu:.1f} cm > {max_lu:.1f} cm"
            )

    if tariff_code == "EXP":
        exp_cfg = cfg.get("carrier_specific_surcharges", {}).get("EXP", {})
        if exp_cfg.get("overlength_over_350_quote_only"):
            for idx, piece in enumerate(pieces, start=1):
                if float(piece["length_cm"]) > 350.0:
                    reasons.append(
                        f"Packstück {idx}: Länge > 350 cm nur mit Tarifanfrage/Freigabe."
                    )
        if exp_cfg.get("girth_over_500_requires_approval"):
            for idx, piece in enumerate(pieces, start=1):
                metrics = get_piece_metrics(cfg, piece)
                if metrics["girth_plus_length"] > 500.0:
                    reasons.append(
                        f"Packstück {idx}: Gurtmaß > 500 cm nur mit Freigabe/Tarifinfo vorab."
                    )
        if selected_exp_services:
            svc_cfg = exp_cfg.get("extra_services", {})
            for service_key in selected_exp_services:
                service = svc_cfg.get(service_key)
                if service and service.get("quote_only"):
                    if service_key == "inselzustellung":
                        continue
                    reasons.append(
                        f"Zusatzservice '{service['label']}' ist Preis auf Anfrage."
                    )
    return reasons


def calculate_insurance_fee(cfg, declared_goods_value_eur):
    logic = cfg["insurance_logic"]
    included = float(logic["included_value_eur"])
    if declared_goods_value_eur <= included:
        return 0.0
    # Neues Schema: 1,5 ‰ vom gesamten Warenwert.
    if "rate_per_mille_of_declared_value" in logic:
        rate_per_mille = float(logic["rate_per_mille_of_declared_value"])
        return declared_goods_value_eur * (rate_per_mille / 1000.0)

    # Fallback fuer alte Konfigurationen.
    if "rate_pct_over_included" in logic:
        over_value = declared_goods_value_eur - included
        fee = over_value * (float(logic["rate_pct_over_included"]) / 100.0)
        if "min_fee_eur" in logic:
            fee = max(fee, float(logic["min_fee_eur"]))
        if "max_fee_eur" in logic:
            fee = min(fee, float(logic["max_fee_eur"]))
        return fee

    # Sicherer Default statt KeyError.
    return 0.0


def calculate_case_c_tariff(
    cfg,
    tariff_code,
    pieces,
    selected_services,
    pickup_timing,
    declared_goods_value_eur,
    selected_exp_services=None,
    late_pickup_ctx=None,
    insurance_enabled=False,
):
    tariff = cfg["tariffs"][tariff_code]
    base_total = 0.0
    matched_bands = []
    piece_metrics_list = []
    for piece in pieces:
        piece_metrics = get_piece_metrics(cfg, piece)
        piece_metrics_list.append(piece_metrics)
    # Grundtarif basiert auf dem summierten Abrechnungsgewicht der gesamten Sendung.
    total_billable_weight = sum(m["billable_weight"] for m in piece_metrics_list)
    base_total, matched_band = get_weight_price(
        total_billable_weight, tariff["ground_rates_by_weight_band"]
    )
    if base_total is None:
        return None
    matched_bands.append(matched_band)

    parcel_count = len(pieces)
    fuel_pct = float(tariff["service_surcharges"].get("fuel_surcharge_pct", 0.0))
    fuel_amount = base_total * (fuel_pct / 100.0)

    extras_total = 0.0
    extras_breakdown = []
    services_cfg = cfg["extra_delivery_services"]
    for service_key in selected_services:
        service = services_cfg[service_key]
        applies_to = service.get("applies_to", ["EXP", "LZ48"])
        if tariff_code not in applies_to:
            continue
        price = float(service["price_eur"])
        if service["applies_per"] == "parcel":
            amount = price * parcel_count
        else:
            amount = price
        extras_total += amount
        extras_breakdown.append((service["label"], amount))

    if tariff_code == "EXP" and selected_exp_services:
        exp_cfg = cfg.get("carrier_specific_surcharges", {}).get("EXP", {})
        svc_cfg = exp_cfg.get("extra_services", {})
        for service_key in selected_exp_services:
            service = svc_cfg.get(service_key)
            if not service or service.get("quote_only"):
                continue
            price = float(service["price_eur"])
            if service.get("applies_per") == "parcel":
                amount = price * parcel_count
            else:
                amount = price
            extras_total += amount
            extras_breakdown.append((f"EXP Service - {service['label']}", amount))

    late_cfg = cfg["late_fees"].get(
        pickup_timing, {"label": "Standardanmeldung (bis Cutoff)", "price_eur": 0.0}
    )
    late_fee = float(late_cfg["price_eur"])
    late_pickup_fee = 0.0
    late_pickup_label = None
    pickup_area_fee = 0.0
    pickup_area_label = None

    if late_pickup_ctx is None:
        late_pickup_ctx = {}

    pickup_area = late_pickup_ctx.get("pickup_area")
    shipment_count = int(late_pickup_ctx.get("shipment_count", 1))
    area_rules = cfg.get("pickup_area_rules", {})
    if pickup_area in area_rules:
        area_rule = area_rules[pickup_area]
        base_area_fee = float(area_rule.get("base_fee_eur", 0.0))
        if pickup_area == "B":
            threshold_map = area_rule.get("waiver_threshold_shipments", {})
            threshold = int(threshold_map.get(tariff_code, 9999))
            if shipment_count >= threshold:
                base_area_fee = 0.0
        pickup_area_fee = base_area_fee
        if pickup_area_fee > 0:
            pickup_area_label = f"Abholgebiet {pickup_area}"
    late_rules = cfg.get("late_pickup_rules", {})
    applies_to = late_rules.get("applies_to", [])
    if tariff_code in applies_to and (
        late_pickup_ctx.get("is_late_registration", False)
        or late_pickup_ctx.get("is_late_pickup", False)
    ):
        area = late_pickup_ctx.get("pickup_area", "A")
        window_label = late_pickup_ctx.get("pickup_window")
        additional_shipments = int(late_pickup_ctx.get("additional_shipments", 0))
        self_dropoff_after_19 = bool(late_pickup_ctx.get("self_dropoff_after_19", False))
        is_late_registration = bool(late_pickup_ctx.get("is_late_registration", False))
        is_late_pickup = bool(late_pickup_ctx.get("is_late_pickup", False))

        if is_late_registration:
            reg_fees = late_rules.get("late_registration_fee_by_area_eur", {})
            late_fee = float(reg_fees.get(area, late_fee))
            late_cfg = {"label": f"Spaetanmeldung Gebiet {area}", "price_eur": late_fee}

        for row in late_rules.get("time_window_fees", []):
            if row["label"] == window_label:
                if area == "A":
                    late_pickup_fee = float(row["fee_area_a_eur"])
                else:
                    late_pickup_fee = float(row["fee_area_b_eur"])
                break

        late_pickup_fee += float(late_rules.get("additional_shipment_fee_eur", 0.0)) * max(
            0, additional_shipments
        )

        if area == "A" and self_dropoff_after_19:
            late_pickup_fee = max(
                0.0,
                late_pickup_fee
                - float(late_rules.get("self_dropoff_after_19_discount_area_a_eur", 0.0)),
            )
        late_pickup_label = f"Spaetabholung Gebiet {area} ({window_label})"

        if not is_late_pickup:
            late_pickup_fee = 0.0
            late_pickup_label = None

    over = cfg["oversized_shipment_surcharges"]
    oversize_count = 0
    for piece, piece_metrics in zip(pieces, piece_metrics_list):
        lu = piece_metrics["girth_plus_length"]
        if (
            piece_metrics["billable_weight"] > float(over["weight_over_kg"])
            or piece["length_cm"] > float(over["length_over_cm"])
            or lu > float(over["girth_plus_length_over_cm"])
        ):
            oversize_count += 1

    oversize_fee = 0.0
    if oversize_count > 0:
        if over["applies_per"] == "parcel":
            oversize_fee = float(over["surcharge_eur"]) * oversize_count
        else:
            oversize_fee = float(over["surcharge_eur"])

    carrier_surcharge_total = 0.0
    carrier_surcharge_breakdown = []
    carrier_surcharges = cfg.get("carrier_specific_surcharges", {}).get(tariff_code, {})

    if tariff_code == "LZ48":
        oversized_dimension_count = sum(
            1
            for metrics in piece_metrics_list
            if metrics["longest_side_cm"] > UPS_LONGEST_SIDE_SURCHARGE_THRESHOLD_CM
            or metrics["second_longest_side_cm"] > UPS_SECOND_LONGEST_SIDE_SURCHARGE_THRESHOLD_CM
        )
        if oversized_dimension_count > 0:
            amount = UPS_DIMENSION_SURCHARGE_EUR_PER_PIECE * oversized_dimension_count
            carrier_surcharge_total += amount
            carrier_surcharge_breakdown.append(("UPS Maßzuschlag >100/76 cm", amount))

        over_25_50 = float(
            carrier_surcharges.get("over_25_to_50_kg_surcharge_eur_per_piece", 0.0)
        )
        if over_25_50 > 0:
            count_25_50 = sum(
                1
                for metrics in piece_metrics_list
                if metrics["billable_weight"] > 25.0 and metrics["billable_weight"] <= 50.0
            )
            if count_25_50 > 0:
                amount = over_25_50 * count_25_50
                carrier_surcharge_total += amount
                carrier_surcharge_breakdown.append(("LZ48 >25kg bis 50kg", amount))

        long_threshold = float(
            carrier_surcharges.get("long_piece_threshold_length_cm", 9999.0)
        )
        long_fee = float(
            carrier_surcharges.get("long_piece_surcharge_eur_per_piece", 0.0)
        )
        if long_fee > 0:
            long_count = sum(
                1 for piece in pieces if float(piece["length_cm"]) > long_threshold
            )
            if long_count > 0:
                amount = long_fee * long_count
                carrier_surcharge_total += amount
                carrier_surcharge_breakdown.append(("Längenzuschlag", amount))

    if tariff_code == "EXP":
        non_conv_50 = float(
            carrier_surcharges.get("non_conveyable_over_50kg_surcharge_eur_per_piece", 0.0)
        )
        non_conv_100 = float(
            carrier_surcharges.get("non_conveyable_over_100kg_surcharge_eur_per_piece", 0.0)
        )
        extra_per_kg_over_100 = float(
            carrier_surcharges.get("over_100kg_additional_eur_per_kg", 0.0)
        )
        for metrics in piece_metrics_list:
            if metrics["billable_weight"] > 100 and non_conv_100 > 0:
                amount = non_conv_100 + (
                    (metrics["billable_weight"] - 100.0) * extra_per_kg_over_100
                )
                carrier_surcharge_total += amount
                carrier_surcharge_breakdown.append(("Nichtbandservice >100kg", amount))
            elif metrics["billable_weight"] > 50 and non_conv_50 > 0:
                carrier_surcharge_total += non_conv_50
                carrier_surcharge_breakdown.append(("Nichtbandservice >50kg", non_conv_50))

        for rule in carrier_surcharges.get("overlength_rules", []):
            min_excl = float(rule["min_length_exclusive_cm"])
            max_incl = float(rule["max_length_inclusive_cm"])
            matching_count = sum(
                1
                for piece in pieces
                if float(piece["length_cm"]) > min_excl
                and float(piece["length_cm"]) <= max_incl
            )
            if matching_count > 0:
                first_fee = float(rule.get("first_piece_surcharge_eur", 0.0))
                additional_fee = float(rule.get("additional_piece_surcharge_eur", first_fee))
                amount = first_fee + max(0, matching_count - 1) * additional_fee
                carrier_surcharge_total += amount
                carrier_surcharge_breakdown.append(
                    (
                        f"Überlänge {int(min_excl)+1}-{int(max_incl)} cm ({matching_count} PS)",
                        amount,
                    )
                )

        for metrics in piece_metrics_list:
            piece_girth = metrics["girth_plus_length"]
            applicable_girth_fee = 0.0
            for rule in carrier_surcharges.get("girth_rules", []):
                min_excl = float(rule["min_girth_exclusive_cm"])
                max_incl = float(rule["max_girth_inclusive_cm"])
                if piece_girth > min_excl and piece_girth <= max_incl:
                    applicable_girth_fee = max(
                        applicable_girth_fee, float(rule["surcharge_eur_per_piece"])
                    )
            if applicable_girth_fee > 0:
                carrier_surcharge_total += applicable_girth_fee
                carrier_surcharge_breakdown.append(("Gurtmaß-Zuschlag", applicable_girth_fee))

    insurance_fee = (
        calculate_insurance_fee(cfg, declared_goods_value_eur) if insurance_enabled else 0.0
    )
    total = (
        base_total
        + fuel_amount
        + extras_total
        + late_fee
        + pickup_area_fee
        + late_pickup_fee
        + oversize_fee
        + carrier_surcharge_total
        + insurance_fee
    )

    return {
        "carrier_label": tariff["carrier_label"],
        "tariff_code": tariff_code,
        "service_label": tariff.get("service_label", tariff_code),
        "matched_bands": matched_bands,
        "piece_metrics": piece_metrics_list,
        "base_total": base_total,
        "fuel_pct": fuel_pct,
        "fuel_amount": fuel_amount,
        "extras_breakdown": extras_breakdown,
        "extras_total": extras_total,
        "late_label": late_cfg["label"],
        "late_fee": late_fee,
        "pickup_area_label": pickup_area_label,
        "pickup_area_fee": pickup_area_fee,
        "late_pickup_label": late_pickup_label,
        "late_pickup_fee": late_pickup_fee,
        "oversize_fee": oversize_fee,
        "carrier_surcharge_breakdown": carrier_surcharge_breakdown,
        "carrier_surcharge_total": carrier_surcharge_total,
        "insurance_fee": insurance_fee,
        "total": total,
    }


