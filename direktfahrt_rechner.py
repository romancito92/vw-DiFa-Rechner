from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from auth_helpers import (
    get_oidc_configuration_error,
    get_user_display_name,
    get_user_email,
    get_user_role,
    is_logged_in,
    is_user_authorized,
    login_button_label,
    render_access_denied,
)

from config import (
    RATE_TABLE,
    ORS_PROFILE_LABELS,
    VEHICLE_TO_ORS_PROFILE,
    ORS_PROFILE_TO_VEHICLE,
    TANKERKOENIG_DEFAULT_LOCATION,
    TANKERKOENIG_DEFAULT_RADIUS_KM,
    get_auth_settings,
    get_ors_api_key,
    get_tankerkoenig_api_key,
)
from logging_helpers import configure_app_logger
from ors_helpers import get_ors_address_suggestions, get_ors_distance_and_duration
from tankerkoenig_helpers import get_nearby_diesel_price
from ui_helpers import (
    format_eur,
    format_eur_per_km,
    format_duration_compact,
    render_app_styles,
    render_confidence_box,
    render_case_c_recommendation,
    render_copy_text_button,
    build_case_c_offer_text,
    build_case_c_price_rows,
    build_case_c_price_bullets,
    render_case_c_plausibility_checks,
    render_case_c_carrier_header,
    render_icon_toggle,
    render_method_card,
    render_recommendation_card,
)
from logic_direct import (
    get_distance_class,
    calculate_case_a,
    calculate_case_b_ek,
    calculate_case_b_table,
    round_down_to_odd_price,
)
from logic_parcel import (
    load_parcel_config,
    get_piece_metrics,
    determine_pickup_area,
    evaluate_shipment_eligibility,
    evaluate_carrier_eligibility,
    calculate_case_c_tariff,
)


A_CONSUMPTION_PRESETS = {
    "Standard/manuell": 10.0,
    "Fiat Ducato L4H3": 8.5,
    "Sprinter lang": 10.0,
    "Koffersprinter": 14.0,
}
APP_TIMEZONE = ZoneInfo("Europe/Berlin")
A_MAIN_SITE_ADDRESS = "Heeserstraße 5, 57072 Siegen"







def render_login_gate():
    """Blocks access until a valid internal user is logged in."""
    auth_settings = get_auth_settings()

    if not is_logged_in():
        st.title("Versandwerk Preisrechner [intern]")
        st.caption("Interne Anwendung fuer Preisfindung im Versand- und Transportkontext.")
        st.info("Bitte mit Ihrem internen Versandwerk-Konto anmelden.")
        oidc_configuration_error = get_oidc_configuration_error()
        if oidc_configuration_error:
            st.error(oidc_configuration_error)
            st.caption("Ohne vollstaendige OIDC-Secrets bleibt die App aus Sicherheitsgruenden gesperrt.")
            st.stop()

        if st.button(login_button_label(), key="auth_login_button", type="primary"):
            st.login(auth_settings.provider_key)
        st.stop()

    if not is_user_authorized():
        render_access_denied()
        st.stop()


def render_user_session_bar():
    """Shows the authenticated session and exposes logout."""
    display_name = get_user_display_name()
    email = get_user_email()
    role = get_user_role()
    role_label = "Admin" if role == "admin" else "User"

    info_col, action_col = st.columns([0.8, 0.2], gap="medium", vertical_alignment="center")
    with info_col:
        st.caption(f"Angemeldet als {display_name} ({email}) | Rolle: {role_label}")
    with action_col:
        if st.button("Abmelden", key="auth_logout_button", width="stretch"):
            st.logout()


def render_app_header():
    """Render title with optional logo in the top-right corner."""
    render_app_styles()
    st.markdown(
        """
        <style>
        div[data-testid="stImage"] img {
            border-radius: 0 !important;
            object-fit: contain !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    left_col, right_col = st.columns([4.8, 1.4], gap="medium", vertical_alignment="center")
    with left_col:
        st.title("Versandwerk Preisrechner [intern]")
    with right_col:
        logo_path = Path(__file__).with_name("assets").joinpath("logo.png")
        if logo_path.exists():
            st.image(str(logo_path), width=220)


def sync_b_profile_from_vehicle():
    """Synchronisiert ORS-Profil aus Fahrzeugtyp in Modus B."""
    vehicle_type = st.session_state.get("b_vehicle_type")
    mapped_profile = VEHICLE_TO_ORS_PROFILE.get(vehicle_type, "driving-car")
    st.session_state["b_ors_profile"] = mapped_profile


def sync_b_vehicle_from_profile():
    """Synchronisiert Fahrzeugtyp aus ORS-Profil in Modus B."""
    profile = st.session_state.get("b_ors_profile")
    mapped_vehicle = ORS_PROFILE_TO_VEHICLE.get(profile, "Transporter / Sprinter")
    st.session_state["b_vehicle_type"] = mapped_vehicle


def sync_a_consumption_from_preset():
    """Synchronisiert Verbrauch aus Fahrzeug-Preset in Modus A."""
    preset = st.session_state.get("a_consumption_preset", "Standard/manuell")
    preset_value = A_CONSUMPTION_PRESETS.get(preset)
    if preset_value is not None:
        st.session_state["a_consumption_manual_override"] = False
        st.session_state["a_diesel_consumption"] = preset_value


def mark_a_consumption_manual_override():
    """Merkt sich, dass der Verbrauch manuell überschrieben wurde."""
    st.session_state["a_consumption_manual_override"] = True


def sync_a_vehicle_for_liftgate():
    """Hebebühnenfahrten laufen standardmäßig auf Koffersprinter."""
    if st.session_state.get("a_liftgate_required"):
        st.session_state["a_consumption_preset"] = "Koffersprinter"
        sync_a_consumption_from_preset()


def fetch_a_diesel_price_from_tankerkoenig():
    """Lädt einen Dieselpreis nahe dem Hauptstandort in Siegen."""
    fetched_at = datetime.now(APP_TIMEZONE)
    tankerkoenig_api = get_tankerkoenig_api_key()
    try:
        result = get_nearby_diesel_price(
            tankerkoenig_api.value,
            TANKERKOENIG_DEFAULT_LOCATION["lat"],
            TANKERKOENIG_DEFAULT_LOCATION["lng"],
            TANKERKOENIG_DEFAULT_RADIUS_KM,
        )
    except Exception as exc:
        st.session_state["a_fuel_fetch_error"] = str(exc)
        st.session_state.pop("a_fuel_fetch_result", None)
        return

    result["fetched_at"] = fetched_at.strftime("%d.%m.%Y %H:%M:%S")
    result["fetched_at_iso"] = fetched_at.isoformat()
    result["api_key_source"] = tankerkoenig_api.source
    st.session_state["a_diesel_current"] = round(result["price"], 3)
    st.session_state["a_fuel_fetch_result"] = result
    st.session_state.pop("a_fuel_fetch_error", None)


def ensure_a_diesel_price_loaded(max_age_minutes=15):
    """Lädt den Dieselpreis automatisch, wenn noch keiner vorliegt oder er veraltet ist."""
    result = st.session_state.get("a_fuel_fetch_result")
    if not result:
        fetch_a_diesel_price_from_tankerkoenig()
        return

    fetched_at_iso = result.get("fetched_at_iso")
    if not fetched_at_iso:
        fetch_a_diesel_price_from_tankerkoenig()
        return

    try:
        fetched_at = datetime.fromisoformat(fetched_at_iso)
    except ValueError:
        fetch_a_diesel_price_from_tankerkoenig()
        return

    age_minutes = (datetime.now(APP_TIMEZONE) - fetched_at).total_seconds() / 60
    if age_minutes >= max_age_minutes:
        fetch_a_diesel_price_from_tankerkoenig()


def fetch_case_a_ors_totals(start_address, target_address, api_key, profile, include_approach):
    """Berechnet optional die Anfahrt vom Hauptstandort plus die eigentliche Strecke."""
    route_segments = []

    if include_approach:
        approach_km, approach_minutes = get_ors_distance_and_duration(
            A_MAIN_SITE_ADDRESS,
            start_address,
            api_key,
            profile,
        )
        route_segments.append(
            {
                "label": "Hauptstandort -> Startadresse",
                "distance_km": approach_km,
                "duration_minutes": approach_minutes,
            }
        )

    trip_km, trip_minutes = get_ors_distance_and_duration(
        start_address,
        target_address,
        api_key,
        profile,
    )
    route_segments.append(
        {
            "label": "Startadresse -> Zieladresse",
            "distance_km": trip_km,
            "duration_minutes": trip_minutes,
        }
    )

    total_distance_km = sum(segment["distance_km"] for segment in route_segments)
    total_duration_minutes = sum(segment["duration_minutes"] for segment in route_segments)
    return total_distance_km, total_duration_minutes, route_segments




def address_input_with_autofill(label, query_key, api_key):
    """Ein Eingabefeld + klickbare Vorschläge darunter."""
    pending_key = f"{query_key}__pending"
    if pending_key in st.session_state:
        st.session_state[query_key] = st.session_state[pending_key]
        del st.session_state[pending_key]

    query = st.text_input(label, key=query_key)
    selected = query.strip()

    if api_key and len(selected) >= 3:
        try:
            suggestions = get_ors_address_suggestions(selected, api_key)
        except Exception:
            suggestions = []

        if suggestions:
            st.caption(f"Vorschläge für {label}:")
            shown = suggestions[:4]
            for i, suggestion in enumerate(shown):
                if st.button(
                    suggestion,
                    key=f"{query_key}_sugg_{i}",
                    width="stretch",
                ):
                    st.session_state[pending_key] = suggestion
                    st.rerun()

    return st.session_state.get(query_key, selected).strip()















































def show_case_c():
    st.subheader("C - Paketversand Deutschland")
    st.caption("Nur für innerdeutsche und pakettaugliche Sendungen (MVP).")

    try:
        cfg = load_parcel_config()
    except Exception as exc:
        st.error(f"Tarifkonfiguration konnte nicht geladen werden: {exc}")
        return
    meta = cfg.get("meta", {})
    st.caption(
        f"Tarifstand: v{meta.get('version', '-')}"
        + (f" | Stand: {meta.get('tariff_date')}" if meta.get("tariff_date") else "")
    )

    if "c_piece_ids" not in st.session_state:
        st.session_state["c_piece_ids"] = [0]
    if "c_piece_next_id" not in st.session_state:
        st.session_state["c_piece_next_id"] = 1
    if "c_form_version" not in st.session_state:
        st.session_state["c_form_version"] = 0

    # Box 1: Sendungsdaten
    with st.container(border=True):
        st.markdown("### 1. Sendungsdaten")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
        with c1:
            st.selectbox(
                "Zielland",
                ["DE - Deutschland"],
                index=0,
                disabled=True,
                key="c_country_ui",
            )
            country_code = "DE"
        with c2:
            pickup_postal_code = st.text_input(
                "Abhol-PLZ",
                value=st.session_state.get("c_pickup_postal_code", "57072"),
                key="c_pickup_postal_code",
                max_chars=5,
            )
        with c3:
            st.metric("Anzahl Packstücke", len(st.session_state["c_piece_ids"]))
        with c4:
            if st.button("🔄 Neue Sendung", key="c_reset_shipment", width="stretch"):
                next_form_version = int(st.session_state.get("c_form_version", 0)) + 1
                for key in list(st.session_state.keys()):
                    if key.startswith("c_"):
                        del st.session_state[key]
                st.session_state["c_form_version"] = next_form_version
                st.rerun()

    declared_goods_value = 0.0
    insurance_enabled = False

    pickup_area = determine_pickup_area(cfg, pickup_postal_code)
    if pickup_area is None:
        st.warning("Bitte eine gültige 5-stellige Abhol-PLZ eingeben.")
        return
    st.caption(f"Abholgebiet laut PLZ: {pickup_area}")
    if pickup_area == "C":
        note = cfg.get("pickup_area_rules", {}).get("C", {}).get("note")
        if note:
            st.warning(f"Gebiet C: {note}")

    # Box 2: Packstück-Daten
    with st.container(border=True):
        st.markdown("### 2. Packstück-Daten")
        pieces = []
        piece_ids = list(st.session_state["c_piece_ids"])
        form_version = int(st.session_state.get("c_form_version", 0))
        for idx, piece_id in enumerate(piece_ids, start=1):
            with st.expander(f"Packstück {idx}", expanded=(idx == 1)):
                p1, p2, p3, p4, p5 = st.columns([1, 1, 1, 1, 0.8])
                with p1:
                    p_weight = st.number_input(
                        "Gewicht (kg)",
                        min_value=0.1,
                        value=5.0,
                        step=0.1,
                        key=f"c_v{form_version}_piece_{piece_id}_weight",
                    )
                with p2:
                    p_length = st.number_input(
                        "Länge (cm)",
                        min_value=1.0,
                        value=40.0,
                        step=1.0,
                        key=f"c_v{form_version}_piece_{piece_id}_length",
                    )
                with p3:
                    p_width = st.number_input(
                        "Breite (cm)",
                        min_value=1.0,
                        value=30.0,
                        step=1.0,
                        key=f"c_v{form_version}_piece_{piece_id}_width",
                    )
                with p4:
                    p_height = st.number_input(
                        "Höhe (cm)",
                        min_value=1.0,
                        value=20.0,
                        step=1.0,
                        key=f"c_v{form_version}_piece_{piece_id}_height",
                    )
                with p5:
                    st.caption("")
                    if idx > 1 and st.button("🗑️ Löschen", key=f"c_delete_piece_{piece_id}", width="stretch"):
                        st.session_state["c_piece_ids"] = [pid for pid in st.session_state["c_piece_ids"] if pid != piece_id]
                        st.rerun()
                pieces.append(
                    {
                        "weight_kg": float(p_weight),
                        "length_cm": float(p_length),
                        "width_cm": float(p_width),
                        "height_cm": float(p_height),
                    }
                )

                if idx == len(piece_ids):
                    if st.button("➕ Packstück hinzufügen", key=f"c_add_piece_after_{piece_id}"):
                        next_id = int(st.session_state.get("c_piece_next_id", 1))
                        st.session_state["c_piece_ids"].append(next_id)
                        st.session_state["c_piece_next_id"] = next_id + 1
                        st.rerun()

        st.caption("IATA-Formel: L x B x H (cm) / 5000 = Volumengewicht (kg)")
        st.caption("Gurtmaß: Länge + (2 x Breite) + (2 x Höhe)")

        piece_rows = []
        for idx, piece in enumerate(pieces, start=1):
            metrics = get_piece_metrics(cfg, piece)
            piece_rows.append(
                {
                    "Packstück": idx,
                    "Real kg": f"{metrics['real_weight']:.1f}",
                    "Volumen kg": f"{metrics['volume_weight']:.1f}",
                    "Abrechnung kg": f"{metrics['billable_weight']:.1f}",
                    "Gurtmaß cm": f"{metrics['girth_plus_length']:.1f}",
                }
            )
        st.dataframe(piece_rows, width="stretch", hide_index=True)

    selected_services = []
    selected_exp_services = []
    island_service_selected = False
    lz48_blocked_by_exp_timing = False
    is_pallet = False
    is_non_parcel = False
    is_late_registration = False
    is_late_pickup = False
    has_additional_shipments = False
    self_dropoff_after_19 = False
    pickup_window_options = [
        row["label"] for row in cfg.get("late_pickup_rules", {}).get("time_window_fees", [])
    ]
    pickup_window = pickup_window_options[0] if pickup_window_options else None
    pickup_timing = "standard"

    with st.expander("Erweitert (Extras & Co)", expanded=False):
        declared_goods_value = st.number_input(
            "Warenwert (EUR)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key="c_goods_value",
        )
        insurance_enabled = st.checkbox(
            "Höherversicherung aktivieren",
            value=False,
            key="c_insurance_enabled",
            help="Nur bei aktivem Haken und Warenwert über 250 EUR wird ein Zuschlag berechnet.",
        )
        st.caption("Zusatzservices, Spätabholung und Spezialoptionen")

        service_keys = list(cfg["extra_delivery_services"].keys())
        if "c_services" in st.session_state:
            st.session_state["c_services"] = [
                key for key in st.session_state["c_services"] if key in service_keys
            ]

        exp_services_cfg = (
            cfg.get("carrier_specific_surcharges", {})
            .get("EXP", {})
            .get("extra_services", {})
        )
        exp_service_keys = list(exp_services_cfg.keys())
        if "c_exp_services" in st.session_state:
            st.session_state["c_exp_services"] = [
                key for key in st.session_state["c_exp_services"] if key in exp_service_keys
            ]
        time_service_keys = [k for k in exp_service_keys if k.startswith("time_")]
        day_service_keys = [k for k in ["saturday_exp", "sunday_holiday"] if k in exp_service_keys]
        if "c_exp_time_service" not in st.session_state:
            st.session_state["c_exp_time_service"] = ""
        if st.session_state["c_exp_time_service"] not in ([""] + time_service_keys):
            st.session_state["c_exp_time_service"] = ""
        if "c_exp_day_service" not in st.session_state:
            st.session_state["c_exp_day_service"] = ""
        if st.session_state["c_exp_day_service"] not in ([""] + day_service_keys):
            st.session_state["c_exp_day_service"] = ""

        s1, s2, s3 = st.columns(3)
        with s1:
            selected_services = st.multiselect(
                "Optionale Zusatzleistungen",
                service_keys,
                format_func=lambda k: cfg["extra_delivery_services"][k]["label"],
                key="c_services",
                placeholder="Extras auswählen",
            )
        with s2:
            st.caption("Spätanmeldung wird über die Checkbox unten gesteuert.")
        with s3:
            is_pallet = st.checkbox("Palettensendung", value=False, key="c_is_pallet")
            is_non_parcel = st.checkbox("Nicht pakettauglich", value=False, key="c_non_parcel")

        exp_time_choice = st.selectbox(
            "EXP Terminzustellung (exklusiv)",
            [""] + time_service_keys,
            index=([""] + time_service_keys).index(st.session_state["c_exp_time_service"]),
            format_func=lambda k: "Kein Terminservice" if k == "" else exp_services_cfg[k]["label"],
            key="c_exp_time_service",
        )
        exp_day_choice = st.selectbox(
            "EXP Zustelltag",
            [""] + day_service_keys,
            index=([""] + day_service_keys).index(st.session_state["c_exp_day_service"]),
            format_func=lambda k: "Werktag (Standard)" if k == "" else exp_services_cfg[k]["label"],
            key="c_exp_day_service",
        )
        selected_exp_non_time_services = st.multiselect(
            "EXP Zusatzservices (ohne Termin-/Tagesservice)",
            [k for k in exp_service_keys if k not in time_service_keys and k not in day_service_keys],
            format_func=lambda k: exp_services_cfg[k]["label"],
            key="c_exp_services",
            placeholder="Extras auswählen",
        )
        selected_exp_services = list(selected_exp_non_time_services)
        if exp_time_choice:
            selected_exp_services.append(exp_time_choice)
        if exp_day_choice:
            selected_exp_services.append(exp_day_choice)
        island_service_selected = "inselzustellung" in selected_exp_services

        # Wenn EXP-Terminservices gewählt sind, ist LZ48 automatisch ausgeschlossen.
        exp_time_commitment_keys = {"time_08", "time_09", "time_10", "time_12", "fixtermin"}
        lz48_blocked_by_exp_timing = any(
            service_key in exp_time_commitment_keys for service_key in selected_exp_services
        )

        st.markdown("**Spätabholung (EXP & LZ48)**")
        lp1, lp2, lp3, lp4 = st.columns(4)
        with lp1:
            is_late_registration = st.checkbox(
                "Spätanmeldung",
                value=False,
                key="c_late_registration",
                help="Cutoff: nach 17 Uhr in Gebiet A, nach 16 Uhr in Gebiet B.",
            )
        with lp2:
            is_late_pickup = st.checkbox(
                "Spätabholung erforderlich",
                value=False,
                key="c_late_pickup_required",
            )
        with lp3:
            st.text_input(
                "Gebiet (aus PLZ)",
                value=pickup_area,
                key="c_pickup_area_display",
                disabled=True,
            )
        with lp4:
            pickup_window = st.selectbox(
                "Abholfenster",
                pickup_window_options,
                index=0,
                key="c_pickup_window",
                disabled=not is_late_pickup,
            )

        st.info("Cutoff: nach 17 Uhr in Gebiet A, nach 16 Uhr in Gebiet B.")
        has_additional_shipments = st.checkbox(
            "Weitere Sendungen in dieser Abholung?",
            value=False,
            key="c_has_additional_shipments",
            help="Wenn beim selben Kunden weitere Sendungen spät abgeholt werden, fällt dieser Service nur einmalig an.",
            disabled=not is_late_pickup,
        )
        self_dropoff_after_19 = st.checkbox(
            "Selbstanlieferung ab 19 Uhr (nur Gebiet A)",
            value=False,
            key="c_self_dropoff_after_19",
            disabled=(not is_late_pickup) or pickup_area != "A",
        )
        pickup_timing = "late_registration" if is_late_registration else "standard"

    blocking, warnings = evaluate_shipment_eligibility(
        cfg, country_code, pieces, is_pallet, is_non_parcel
    )
    if warnings:
        for msg in warnings:
            st.warning(msg)
    if blocking:
        st.error("Sendung nicht für Modus C geeignet:")
        for msg in blocking:
            st.write(f"- {msg}")
        st.info("Empfehlung: bitte Modus A/B oder Speditionsprozess nutzen.")
        return

    exp_reasons = evaluate_carrier_eligibility(
        cfg, "EXP", pieces, selected_exp_services
    )
    lz48_reasons = evaluate_carrier_eligibility(cfg, "LZ48", pieces, [])
    if is_pallet:
        lz48_reasons.append("Palettensendung ist für LZ48 nicht möglich.")
    if lz48_blocked_by_exp_timing:
        lz48_reasons.append(
            "Ausgewählter EXP-Terminservice (z. B. 8/9/10/12 Uhr oder Fixtermin) macht LZ48 unzulässig."
        )

    needs_deku_check = False
    deku_reasons = []
    if is_pallet:
        needs_deku_check = True
        deku_reasons.append("palettierte Sendung")
    if any(float(piece["length_cm"]) > 270.0 for piece in pieces):
        needs_deku_check = True
        deku_reasons.append("Länge über 270 cm")
    if any(get_piece_metrics(cfg, piece)["billable_weight"] > 50.0 for piece in pieces):
        needs_deku_check = True
        deku_reasons.append("Abrechnungsgewicht über 50 kg")
    if needs_deku_check:
        st.warning(
            "Wichtiger Hinweis für Dispo: Vor Beauftragung bitte zwingend mit der DeKu-Station klären, "
            f"ob die Zustellung möglich ist ({', '.join(deku_reasons)})."
        )
    if island_service_selected:
        st.warning(
            "Inselzustellung ist möglicherweise realisierbar, aber nur nach expliziter Prüfung mit der DeKu-Station "
            "(Preis auf Anfrage / manuelle Freigabe)."
        )
    render_case_c_plausibility_checks(
        exp_reasons,
        lz48_reasons,
        needs_deku_check,
        island_service_selected,
        is_late_registration,
        is_late_pickup,
        insurance_enabled,
        declared_goods_value,
    )

    exp = None if exp_reasons else calculate_case_c_tariff(
        cfg,
        "EXP",
        pieces,
        selected_services,
        pickup_timing,
        declared_goods_value,
        selected_exp_services,
        {
            "is_late_registration": is_late_registration,
            "is_late_pickup": is_late_pickup,
            "pickup_area": pickup_area,
            "pickup_window": pickup_window,
            "shipment_count": 2 if has_additional_shipments else 1,
            "additional_shipments": 0,
            "self_dropoff_after_19": self_dropoff_after_19,
        },
        insurance_enabled=insurance_enabled,
    )
    lz48 = None if lz48_reasons else calculate_case_c_tariff(
        cfg,
        "LZ48",
        pieces,
        selected_services,
        pickup_timing,
        declared_goods_value,
        [],
        {
            "is_late_registration": is_late_registration,
            "is_late_pickup": is_late_pickup,
            "pickup_area": pickup_area,
            "pickup_window": pickup_window,
            "shipment_count": 2 if has_additional_shipments else 1,
            "additional_shipments": 0,
            "self_dropoff_after_19": self_dropoff_after_19,
        },
        insurance_enabled=insurance_enabled,
    )

    with st.container(border=True):
        st.markdown("### 3. Tarifvergleich (Ergebnis)")
        lz48_not_offerable_vs_exp = (
            exp is not None and lz48 is not None and lz48["total"] >= exp["total"]
        )
        diff_pct = None
        if exp is not None and lz48 is not None:
            price_diff = abs(exp["total"] - lz48["total"])
            price_ref = min(exp["total"], lz48["total"]) if min(exp["total"], lz48["total"]) > 0 else 1.0
            diff_pct = (price_diff / price_ref) * 100
        t1, t2 = st.columns(2)
        for col, carrier_code, result, reasons in [
            (t1, "EXP", exp, exp_reasons),
            (t2, "LZ48", lz48, lz48_reasons),
        ]:
            with col:
                carrier_label = cfg["tariffs"][carrier_code]["carrier_label"]
                service_label = cfg["tariffs"][carrier_code].get("service_label", carrier_code)

                if reasons:
                    render_case_c_carrier_header(
                        carrier_label,
                        service_label,
                        carrier_code,
                        "Nicht möglich",
                        muted=True,
                    )
                    st.error("Nicht möglich für diese Sendung.")
                    for reason in reasons:
                        st.write(f"- {reason}")
                elif result is None:
                    render_case_c_carrier_header(
                        carrier_label,
                        service_label,
                        carrier_code,
                        "Nicht möglich",
                        muted=True,
                    )
                    st.error("Kein gültiges Gewichtsband für diese Sendung.")
                else:
                    alternative_result = None
                    if carrier_code == "EXP":
                        if (
                            lz48 is not None
                            and exp is not None
                            and lz48["total"] < exp["total"]
                        ):
                            alternative_result = lz48
                    elif carrier_code == "LZ48":
                        if (
                            exp is not None
                            and lz48 is not None
                            and exp["total"] < lz48["total"]
                        ):
                            alternative_result = exp
                    muted_product = False
                    if carrier_code == "LZ48" and exp is not None and lz48 is not None:
                        muted_product = lz48_not_offerable_vs_exp or (diff_pct is not None and diff_pct < 25)
                    elif carrier_code == "EXP" and exp is not None and lz48 is None:
                        muted_product = False

                    status_label = "Möglich"
                    if carrier_code == "LZ48" and lz48_not_offerable_vs_exp:
                        status_label = "Möglich, aber nicht empfohlen"
                    elif carrier_code == "LZ48" and diff_pct is not None and diff_pct < 25 and exp is not None:
                        status_label = "Möglich als Alternative"

                    render_case_c_carrier_header(
                        carrier_label,
                        service_label,
                        carrier_code,
                        status_label,
                        muted=muted_product,
                    )

                    if carrier_code == "LZ48" and lz48_not_offerable_vs_exp:
                        st.markdown(
                            '<div class="vw-casec-note">In diesem Fall bitte EXP priorisieren. '
                            "LZ48 ist nicht günstiger als das schnellere Produkt.</div>",
                            unsafe_allow_html=True,
                        )
                    offer_text = build_case_c_offer_text(result, alternative_result)
                    render_recommendation_card(
                        "Empfohlener Angebotspreis",
                        result["total"],
                        result["carrier_label"],
                        f"{result.get('service_label', carrier_code)} ({carrier_code})",
                        f"c_reco_{carrier_code.lower()}",
                        copy_text=offer_text,
                        subline="Direkt als Angebot für diesen Tarif verwendbar",
                        action_hint="Preis oder Angebotstext direkt kopierbar",
                        muted=muted_product,
                    )
                    with st.expander("Aufschlüsselung (Preisbausteine)", expanded=False):
                        rows = build_case_c_price_rows(result)
                        st.table([{"Baustein": name, "Betrag": format_eur(amount)} for name, amount in rows])
                        render_copy_text_button(
                            "Preisbausteine kopieren",
                            build_case_c_price_bullets(result),
                            f"c_price_blocks_{carrier_code.lower()}",
                        )

        render_case_c_recommendation(exp, lz48)


def show_case_a():
    st.subheader("A - Selbst fahren")

    if "a_km" not in st.session_state:
        st.session_state["a_km"] = 92.0
    if "a_minutes" not in st.session_state:
        st.session_state["a_minutes"] = 72
    st.session_state["a_diesel_base"] = 1.700
    if "a_diesel_current" not in st.session_state:
        st.session_state["a_diesel_current"] = 0.0
    if "a_diesel_consumption" not in st.session_state:
        st.session_state["a_diesel_consumption"] = 10.0
    if "a_consumption_preset" not in st.session_state:
        st.session_state["a_consumption_preset"] = "Standard/manuell"
    if "a_consumption_manual_override" not in st.session_state:
        st.session_state["a_consumption_manual_override"] = False
    if "a_include_hq_approach" not in st.session_state:
        st.session_state["a_include_hq_approach"] = True
    if "a_liftgate_required" not in st.session_state:
        st.session_state["a_liftgate_required"] = False
    if "a_ors_feedback" not in st.session_state:
        st.session_state["a_ors_feedback"] = None

    if (
        st.session_state["a_consumption_preset"] == "Standard/manuell"
        and not st.session_state["a_consumption_manual_override"]
    ):
        st.session_state["a_diesel_consumption"] = 10.0

    st.markdown("### 1. Eingabe")
    input_col, options_col = st.columns([1.15, 1], gap="large")
    with input_col:
        with st.container(border=True):
            st.markdown("**Strecke und Fahrzeit**")
            with st.expander("Entfernung automatisch berechnen (optional)", expanded=True):
                address_col, action_col = st.columns([1.45, 0.85], gap="large")
                ors_api = get_ors_api_key()
                api_key = ors_api.value
                profile = "driving-car"
                if not api_key:
                    st.warning(
                        "ORS API-Key fehlt. Hinterlege `ORS_API_KEY` auf Root-Ebene in den "
                        "Streamlit-Secrets oder alternativ als Umgebungsvariable."
                    )
                with address_col:
                    start_address = address_input_with_autofill(
                        "Startadresse",
                        "a_start_address",
                        api_key,
                    )
                    target_address = address_input_with_autofill(
                        "Zieladresse",
                        "a_target_address",
                        api_key,
                    )
                with action_col:
                    st.toggle(
                        "Anfahrt ab Siegen City einrechnen",
                        key="a_include_hq_approach",
                        help="Berücksichtigt die Anfahrt von Heeserstraße 5, 57072 Siegen zur Startadresse.",
                    )
                    include_hq_approach = st.session_state["a_include_hq_approach"]
                    if st.button(
                        "Distanz und Fahrzeit von ORS holen",
                        key="a_fetch_ors",
                        type="primary",
                    ):
                        if not start_address or not target_address:
                            st.session_state["a_ors_feedback"] = {
                                "state": "error",
                                "message": "Bitte Startadresse und Zieladresse ausfüllen.",
                            }
                        else:
                            with st.status(
                                "ORS-Daten werden gerade abgerufen …",
                                expanded=False,
                            ) as status:
                                try:
                                    distance_km, duration_minutes, route_segments = fetch_case_a_ors_totals(
                                        start_address,
                                        target_address,
                                        api_key,
                                        profile,
                                        include_hq_approach,
                                    )
                                    st.session_state["a_km"] = round(distance_km, 1)
                                    st.session_state["a_minutes"] = int(round(duration_minutes))
                                    st.session_state["a_ors_last_result"] = {"segments": route_segments}
                                    st.session_state["a_ors_feedback"] = {
                                        "state": "success",
                                        "values": f"{distance_km:.1f} km | {duration_minutes:.0f} Minuten",
                                    }
                                    status.update(
                                        label=f"Daten übernommen: {distance_km:.0f} km | {duration_minutes:.0f} Minuten",
                                        state="complete",
                                    )
                                except Exception as exc:
                                    st.session_state["a_ors_feedback"] = {
                                        "state": "error",
                                        "message": f"ORS-Fehler: {exc}",
                                    }
                                    status.update(label="ORS-Abruf fehlgeschlagen.", state="error")

                    ors_feedback = st.session_state.get("a_ors_feedback")
                    if ors_feedback:
                        if ors_feedback["state"] == "error":
                            st.error(ors_feedback["message"])

                ors_last_result = st.session_state.get("a_ors_last_result")
                if ors_last_result:
                    segment_text = " | ".join(
                        f"{segment['label']}: {segment['distance_km']:.1f} km, {segment['duration_minutes']:.0f} min"
                        for segment in ors_last_result.get("segments", [])
                    )
                    st.caption(f"Letzte ORS-Berechnung: {segment_text}")

            col1, col2 = st.columns(2, gap="large")
            with col1:
                km = st.number_input("Kilometer (One-Way)", min_value=0.0, step=1.0, key="a_km")
            with col2:
                one_way_minutes = st.number_input(
                    "Fahrtdauer einfach (Minuten)", min_value=0, step=1, key="a_minutes"
                )
            if one_way_minutes > 240:
                st.warning(
                    "Achtung! Bitte Lenkzeiten von max. 4,5h bei Tourplanung berücksichtigen."
                )

    with options_col:
        with st.container(border=True):
            st.markdown("**Fahrzeug und Zuschläge**")
            option_col1, option_col2 = st.columns([1.05, 0.95], gap="large")
            with option_col1:
                st.selectbox(
                    "Fahrzeug (Preset)",
                    list(A_CONSUMPTION_PRESETS.keys()),
                    key="a_consumption_preset",
                    on_change=sync_a_consumption_from_preset,
                )
            with option_col2:
                liftgate_icon_path = Path(__file__).with_name("assets").joinpath("liftgate_icon.svg")
                render_icon_toggle(
                    "Hebebühnenzuschlag",
                    "a_liftgate_required",
                    "A.1: 39,00 EUR Basis und +0,15 EUR/km. A.2: +20 %. Nur, falls kundenseitig erwünscht/erforderlich.",
                    icon_path=str(liftgate_icon_path) if liftgate_icon_path.exists() else None,
                    on_change=sync_a_vehicle_for_liftgate,
                )

            use_fuel_adjustment = st.checkbox(
                "Spritpreisanpassung anwenden",
                value=True,
                key="a_use_fuel_adjustment",
                help="Berechnet einen Aufschlag pro km aus Dieselpreis-Differenz und Verbrauch.",
            )
            a1_extra_per_km = 0.0
            diesel_diff = 0.0
            consumption_l_per_100km = 0.0
            if use_fuel_adjustment:
                ensure_a_diesel_price_loaded()
                fuel_fetch_error = st.session_state.get("a_fuel_fetch_error")
                fuel_fetch_result = st.session_state.get("a_fuel_fetch_result")
                fuel_button_label = (
                    "Tagespreis aktualisieren" if fuel_fetch_result and not fuel_fetch_error else "Tagespreis laden"
                )

                f1, f2, f3 = st.columns([1, 1.15, 1], gap="medium")
                with f1:
                    diesel_base = st.number_input(
                        "Diesel-Basispreis (EUR/L)",
                        min_value=0.0,
                        step=0.001,
                        format="%.3f",
                        key="a_diesel_base",
                        disabled=True,
                    )
                with f2:
                    st.markdown("**Diesel aktuell (EUR/L)**")
                    if fuel_fetch_result and not fuel_fetch_error:
                        diesel_current = st.session_state["a_diesel_current"]
                        st.metric("Geladener Tagespreis", f"{diesel_current:.3f}")
                        st.caption(
                            f"Abruf vom {fuel_fetch_result['fetched_at']} · "
                            f"{fuel_fetch_result['station_count']} Stationen im Radius"
                        )
                    else:
                        diesel_current = st.session_state["a_diesel_current"]
                        st.info("Noch nicht geladen")
                        st.caption("Bitte Tagespreis aktiv laden, um den Zuschlag auf Basis eines aktuellen Werts zu berechnen.")
                    if st.button(
                        fuel_button_label,
                        key="a_fetch_tankerkoenig",
                        type="primary" if not fuel_fetch_result else "secondary",
                        help="Lädt einen einfachen Durchschnitt der Dieselpreise nahe unserem Hauptstandort in Siegen.",
                    ):
                        with st.spinner("Tagespreis wird geladen ..."):
                            fetch_a_diesel_price_from_tankerkoenig()
                        st.rerun()
                with f3:
                    consumption_l_per_100km = st.number_input(
                        "Verbrauch (L/100 km)",
                        min_value=0.0,
                        step=0.1,
                        key="a_diesel_consumption",
                        on_change=mark_a_consumption_manual_override,
                    )
                if fuel_fetch_error:
                    st.error(f"Tankerkönig-Abruf fehlgeschlagen: {fuel_fetch_error}")
                elif fuel_fetch_result:
                    st.caption(
                        f"Aktueller Dieselpreis (Durchschnitt): {fuel_fetch_result['price']:.3f} EUR/L | "
                        f"Basis: {fuel_fetch_result['station_count']} Stationen "
                        f"im Radius von {fuel_fetch_result['radius_km']:.0f} km"
                        + (
                            f", davon {fuel_fetch_result['open_station_count']} offen"
                            if fuel_fetch_result['open_station_count'] > 0
                            else ""
                        )
                        + " | "
                        f"Abruf: {fuel_fetch_result['fetched_at']}"
                    )
                diesel_diff = max(0.0, diesel_current - diesel_base)
                a1_extra_per_km = diesel_diff * (consumption_l_per_100km / 100.0)
                st.caption(
                    f"Aufschlag A.1: {a1_extra_per_km:.3f} EUR/km "
                    f"(Differenz {diesel_diff:.2f} EUR/L)"
                )
                with st.expander("Technische Hinweise", expanded=False):
                    st.caption(
                        f"Abrufbasis: {TANKERKOENIG_DEFAULT_LOCATION['label']} "
                        f"({TANKERKOENIG_DEFAULT_LOCATION['lat']:.4f}, {TANKERKOENIG_DEFAULT_LOCATION['lng']:.4f}), "
                        f"Radius {TANKERKOENIG_DEFAULT_RADIUS_KM:.0f} km."
                    )
                    st.caption("Der Dieselpreis wird automatisch geladen und etwa alle 15 Minuten aktualisiert.")
                    st.caption(f"ORS-Key-Quelle: {ors_api.source if api_key else 'nicht vorhanden'}")
                    if fuel_fetch_result:
                        st.caption(f"Tankerkönig-Key-Quelle: {fuel_fetch_result['api_key_source']}")
            else:
                diesel_base = st.session_state["a_diesel_base"]
                diesel_current = st.session_state["a_diesel_current"]
                consumption_l_per_100km = st.session_state["a_diesel_consumption"]

    (
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
    ) = calculate_case_a(
        km,
        one_way_minutes,
        a1_extra_per_km,
        st.session_state["a_liftgate_required"],
    )
    rounded_lower_price = round_down_to_odd_price(lower_price)
    rounded_mid_price = round_down_to_odd_price(price_mid)
    rounded_upper_price = round_down_to_odd_price(upper_price)
    rounded_price_a1 = round_down_to_odd_price(price_a1)
    rounded_price_a2 = round_down_to_odd_price(price_a2)

    st.markdown("### 2. Ergebnis")
    lower_source = (
        "km-basiert (A.1 Formel)"
        if price_a1 <= price_a2
        else "zeitbasiert (A.2 Formel)"
    )
    upper_source = (
        "zeitbasiert (A.2 Formel)"
        if price_a1 <= price_a2
        else "km-basiert (A.1 Formel)"
    )
    mid_source = "gemischt (Mittelwert aus A.1 und A.2)"
    if "a_selected_option" not in st.session_state:
        st.session_state["a_selected_option"] = "Mittelwert"

    selected_option = st.session_state["a_selected_option"]
    selected_prices = {
        "Untergrenze": rounded_lower_price,
        "Mittelwert": rounded_mid_price,
        "Obergrenze": rounded_upper_price,
    }
    selected_sources = {
        "Untergrenze": lower_source,
        "Mittelwert": mid_source,
        "Obergrenze": upper_source,
    }
    selected_key = {
        "Untergrenze": "lower",
        "Mittelwert": "mid",
        "Obergrenze": "upper",
    }

    result_col, summary_col = st.columns([1.3, 1], gap="large")
    with result_col:
        with st.container(border=True):
            st.markdown("**VK-Vorschläge**")
            st.caption("Alle folgenden Werte sind VK-Vorschläge (Verkaufspreise) für den Kunden.")
            c1, c2, c3 = st.columns(3, gap="medium")
            with c1:
                st.metric("Untergrenze (VK)", format_eur(rounded_lower_price))
                st.caption(format_eur_per_km(rounded_lower_price, km))
                st.caption(lower_source)
            with c2:
                st.metric("Mittelwert (VK)", format_eur(rounded_mid_price))
                st.caption(format_eur_per_km(rounded_mid_price, km))
                st.caption(mid_source)
            with c3:
                st.metric("Obergrenze (VK)", format_eur(rounded_upper_price))
                st.caption(format_eur_per_km(rounded_upper_price, km))
                st.caption(upper_source)

            st.markdown("**Preis für Angebot auswählen**")
            current_a_option = st.session_state["a_selected_option"]
            s1, s2, s3 = st.columns(3)
            with s1:
                a_lower_active = current_a_option == "Untergrenze"
                if st.button(
                    "✓ Untergrenze" if a_lower_active else "Untergrenze",
                    key="a_pick_lower",
                    width="stretch",
                    type="primary" if a_lower_active else "secondary",
                ):
                    st.session_state["a_selected_option"] = "Untergrenze"
                    st.rerun()
                st.caption(lower_source)
            with s2:
                a_mid_active = current_a_option == "Mittelwert"
                if st.button(
                    "✓ Mittelwert" if a_mid_active else "Mittelwert",
                    key="a_pick_mid",
                    width="stretch",
                    type="primary" if a_mid_active else "secondary",
                ):
                    st.session_state["a_selected_option"] = "Mittelwert"
                    st.rerun()
                st.caption(mid_source)
            with s3:
                a_upper_active = current_a_option == "Obergrenze"
                if st.button(
                    "✓ Obergrenze" if a_upper_active else "Obergrenze",
                    key="a_pick_upper",
                    width="stretch",
                    type="primary" if a_upper_active else "secondary",
                ):
                    st.session_state["a_selected_option"] = "Obergrenze"
                    st.rerun()
                st.caption(upper_source)

    with summary_col:
        with st.container(border=True):
            render_recommendation_card(
                "Empfohlener Preis für das Angebot",
                selected_prices[selected_option],
                selected_option,
                selected_sources[selected_option],
                f"a_{selected_key[selected_option]}",
            )
        with st.container(border=True):
            render_confidence_box(
                rounded_lower_price,
                rounded_upper_price,
                "A-Modell (A.1 vs. A.2)",
            )

    with st.expander("Kurze Herleitung", expanded=False):
        a1_formula_label = "A.1 Formel"
        if use_fuel_adjustment:
            a1_formula_label += " (mit Spritaufschlag)"
        if st.session_state["a_liftgate_required"]:
            a1_formula_label += " + Hebebühnenzuschlag"

        a1_formula_text = (
            f"{a1_base_fee:,.2f} EUR + ({a1_rate_per_km:,.2f} EUR x {km:.1f} km)"
        ).replace(",", "X").replace(".", ",").replace("X", ".")
        if use_fuel_adjustment:
            st.write(
                f"{a1_formula_label}: "
                f"{a1_formula_text} + "
                f"({a1_extra_per_km:.3f} EUR/km x {km:.1f} km) = {format_eur(rounded_price_a1)}"
            )
            st.caption(
                f"Spritaufschlag gesamt: {format_eur(fuel_surcharge_total)} "
                f"(Differenz {diesel_diff:.2f} EUR/L, Verbrauch {consumption_l_per_100km:.1f} L/100 km)"
            )
        else:
            st.write(f"{a1_formula_label}: {a1_formula_text} = {format_eur(rounded_price_a1)}")
        a2_base_price = price_a2 / a2_multiplier if a2_multiplier else price_a2
        st.write(
            "A.2 Formel: "
            f"(2 x {one_way_minutes} min + 30 min) = {total_minutes:.0f} min, "
            f"das entspricht {total_minutes / 60:.2f} h x 60 EUR = {format_eur(a2_base_price)}"
            + (
                f" x {a2_multiplier:.1f} = {format_eur(rounded_price_a2)}"
                if a2_multiplier != 1.0
                else f" -> final {format_eur(rounded_price_a2)}"
            )
        )
        st.write(
            f"Dynamische Sortierung: Untergrenze = {format_eur(rounded_lower_price)}, "
            f"Obergrenze = {format_eur(rounded_upper_price)}"
        )

def show_case_b():
    st.subheader("B - Extern vergeben")

    if "b_km" not in st.session_state:
        st.session_state["b_km"] = 150.0
    if "b_ors_duration_minutes" not in st.session_state:
        st.session_state["b_ors_duration_minutes"] = None
    if "b_ors_profile" not in st.session_state:
        st.session_state["b_ors_profile"] = "driving-car"
    if "b_vehicle_type" not in st.session_state:
        st.session_state["b_vehicle_type"] = ORS_PROFILE_TO_VEHICLE.get(
            st.session_state["b_ors_profile"], "Transporter / Sprinter"
        )
    if "b_ors_feedback" not in st.session_state:
        st.session_state["b_ors_feedback"] = None
    with st.container(border=True):
        st.markdown("### 1. Eingabe")
        with st.expander("Entfernung automatisch berechnen (optional)", expanded=True):
            ors_b_col1, ors_b_col2 = st.columns(2)
            ors_api_b = get_ors_api_key()
            api_key_b = ors_api_b.value
            if not api_key_b:
                st.warning(
                    "ORS API-Key fehlt. Hinterlege `ORS_API_KEY` auf Root-Ebene in den "
                    "Streamlit-Secrets oder alternativ als Umgebungsvariable."
                )
            else:
                st.caption(
                    f"ORS API-Key geladen ({ors_api_b.source}, L\u00e4nge: {len(api_key_b)} Zeichen)."
                )
            _, ors_b_col4 = st.columns([1.2, 1])
            with ors_b_col4:
                profile_b = st.selectbox(
                    "Fahrprofil",
                    ["driving-car", "driving-hgv", "cycling-regular", "foot-walking"],
                    key="b_ors_profile",
                    format_func=lambda p: ORS_PROFILE_LABELS.get(p, p),
                    on_change=sync_b_vehicle_from_profile,
                )

            with ors_b_col1:
                start_address_b = address_input_with_autofill(
                    "Startadresse",
                    "b_start_address",
                    api_key_b,
                )
            with ors_b_col2:
                target_address_b = address_input_with_autofill(
                    "Zieladresse",
                    "b_target_address",
                    api_key_b,
                )

            action_col, feedback_col = st.columns([0.34, 0.66], gap="medium", vertical_alignment="center")
            with feedback_col:
                feedback_placeholder = st.empty()

            with action_col:
                if st.button(
                    "Distanz und Fahrzeit von ORS holen",
                    key="b_fetch_ors",
                    type="primary",
                ):
                    if not start_address_b or not target_address_b:
                        st.session_state["b_ors_feedback"] = {
                            "state": "error",
                            "message": "Bitte Startadresse und Zieladresse ausfüllen.",
                        }
                    else:
                        with feedback_placeholder.container():
                            with st.spinner("ORS-Daten werden gerade abgerufen …"):
                                try:
                                    distance_km_b, duration_minutes_b = get_ors_distance_and_duration(
                                        start_address_b,
                                        target_address_b,
                                        api_key_b,
                                        profile_b,
                                    )
                                    st.session_state["b_km"] = round(distance_km_b, 1)
                                    st.session_state["b_ors_duration_minutes"] = int(
                                        round(duration_minutes_b)
                                    )
                                    st.session_state["b_ors_feedback"] = {
                                        "state": "success",
                                        "values": f"{distance_km_b:.0f} km | {format_duration_compact(duration_minutes_b)}",
                                    }
                                except Exception as exc:
                                    st.session_state["b_ors_feedback"] = {
                                        "state": "error",
                                        "message": f"ORS-Fehler: {exc}",
                                    }

            b_ors_feedback = st.session_state.get("b_ors_feedback")
            if b_ors_feedback:
                if b_ors_feedback["state"] == "success":
                    feedback_placeholder.success(
                        f"Daten übernommen: {b_ors_feedback['values']}",
                    )
                elif b_ors_feedback["state"] == "error":
                    feedback_placeholder.error(b_ors_feedback["message"])

        col1, col2, col3 = st.columns([1, 1.4, 1])
        with col1:
            km = st.number_input("Kilometer", min_value=0.0, step=1.0, key="b_km")
            if st.session_state.get("b_ors_duration_minutes") is not None:
                st.caption(
                    f"Info (ORS): {km:.1f} km | {format_duration_compact(st.session_state['b_ors_duration_minutes'])}"
                )
        with col2:
            vehicle_type = st.selectbox(
                "Fahrzeugtyp",
                list(RATE_TABLE.keys()),
                key="b_vehicle_type",
                on_change=sync_b_profile_from_vehicle,
            )
        with col3:
            ek_price = st.number_input(
                "Einkaufspreis (EK)", min_value=0.0, value=200.0, step=1.0
            )

    ek_prices = calculate_case_b_ek(ek_price)
    distance_class, rates, table_prices = calculate_case_b_table(km, vehicle_type)
    table_ek_min = table_prices["Tabellen-Min"]
    table_ek_mid = table_prices["Tabellen-Mittel"]
    table_ek_max = table_prices["Tabellen-Max"]

    with st.container(border=True):
        st.markdown("### 2. EK-Bewertung")
        ek_col1, ek_col2, ek_col3 = st.columns(3)
        ek_col1.metric("EK-Richtwert Min", format_eur(table_ek_min))
        ek_col2.metric("EK-Richtwert Mittel", format_eur(table_ek_mid))
        ek_col3.metric("EK-Richtwert Max", format_eur(table_ek_max))

        nearest_key = min(
            ("min", "mittel", "max"),
            key=lambda k: abs(
                ek_price
                - {
                    "min": table_ek_min,
                    "mittel": table_ek_mid,
                    "max": table_ek_max,
                }[k]
            ),
        )

        if ek_price <= table_ek_min or nearest_key == "min":
            st.success(
                "Sehr guter EK: liegt nahe am Tabellen-Min oder darunter. "
                "Bitte Partner-Vertrauenswürdigkeit und vollständige Ausführung bestätigen. "
                "Tendenz B.1: eher x1,4 oder x1,5."
            )
        elif ek_price >= table_ek_max or nearest_key == "max":
            st.error(
                "Achtung: EK verhältnismäßig teuer (nahe Tabellen-Max oder darüber). "
                "Wenn möglich weitere Partner und Optionen prüfen. "
                "Tendenz B.1: eher defensiv x1,3."
            )
        else:
            st.info(
                "EK liegt im erwarteten Mittelfeld (nahe Tabellen-Mittel). "
                "Tendenz B.1: x1,3 bis x1,4 je nach Kunden-/Marktsituation."
            )

    with st.container(border=True):
        st.markdown("### 3. VK-Vorschläge")

        b_options = {
            "EK x 1,3": ek_prices["EK x 1,3"],
            "EK x 1,4": ek_prices["EK x 1,4"],
            "EK x 1,5": ek_prices["EK x 1,5"],
        }

        if "b_selected_option" not in st.session_state:
            st.session_state["b_selected_option"] = "EK x 1,4"
        current_b_option = st.session_state["b_selected_option"]
        current_ek_option = current_b_option if current_b_option in b_options else "EK x 1,4"

        method_left, method_right = st.columns(2, gap="large")

        with method_left:
            render_method_card(
                "Verkaufspreis aus realem Einkauf (EK)",
                "Diese Vorschläge leiten sich direkt aus dem tatsächlich vorliegenden Einkaufspreis ab.",
                tone="primary",
            )

            st.caption("Multiplikator-Logik auf den realen EK. Keine zusätzliche Steuerung nötig.")
            st.caption("")

            b1_col1, b1_col2, b1_col3 = st.columns(3)
            with b1_col1:
                b_ek13_active = current_ek_option == "EK x 1,3"
                if st.button(
                    f"{'✓ ' if b_ek13_active else ''}{format_eur(b_options['EK x 1,3'])} ({format_eur_per_km(b_options['EK x 1,3'], km)})",
                    key="b_pick_ek_13",
                    width="stretch",
                    type="primary" if b_ek13_active else "secondary",
                ):
                    st.session_state["b_selected_option"] = "EK x 1,3"
                    st.rerun()
                st.caption("EK x 1,3")
            with b1_col2:
                b_ek14_active = current_ek_option == "EK x 1,4"
                if st.button(
                    f"{'✓ ' if b_ek14_active else ''}{format_eur(b_options['EK x 1,4'])} ({format_eur_per_km(b_options['EK x 1,4'], km)})",
                    key="b_pick_ek_14",
                    width="stretch",
                    type="primary" if b_ek14_active else "secondary",
                ):
                    st.session_state["b_selected_option"] = "EK x 1,4"
                    st.rerun()
                st.caption("EK x 1,4")
            with b1_col3:
                b_ek15_active = current_ek_option == "EK x 1,5"
                if st.button(
                    f"{'✓ ' if b_ek15_active else ''}{format_eur(b_options['EK x 1,5'])} ({format_eur_per_km(b_options['EK x 1,5'], km)})",
                    key="b_pick_ek_15",
                    width="stretch",
                    type="primary" if b_ek15_active else "secondary",
                ):
                    st.session_state["b_selected_option"] = "EK x 1,5"
                    st.rerun()
                st.caption("EK x 1,5")

        with method_right:
            render_method_card(
                "Vergleich mit Richtwerten und Erfahrungswerten",
                "Diese Vorschläge basieren auf geschätzten EK-Richtwerten für eine ähnliche Fahrt.",
                tone="secondary",
            )

            f1, f2, f3 = st.columns(3)
            with f1:
                b2_factor_min = st.selectbox(
                    "Faktor Min",
                    [1.3, 1.4, 1.5],
                    index=0,
                    key="b2_factor_min",
                )
            with f2:
                b2_factor_mid = st.selectbox(
                    "Faktor Mitte",
                    [1.3, 1.4, 1.5],
                    index=1,
                    key="b2_factor_mid",
                )
            with f3:
                b2_factor_max = st.selectbox(
                    "Faktor Max",
                    [1.3, 1.4, 1.5],
                    index=2,
                    key="b2_factor_max",
                )

        b2_vk_min_label = f"B2 Min x{str(b2_factor_min).replace('.', ',')}"
        b2_vk_mid_label = f"B2 Mittel x{str(b2_factor_mid).replace('.', ',')}"
        b2_vk_max_label = f"B2 Max x{str(b2_factor_max).replace('.', ',')}"

        b2_vk_min = round_down_to_odd_price(table_ek_min * b2_factor_min)
        b2_vk_mid = round_down_to_odd_price(table_ek_mid * b2_factor_mid)
        b2_vk_max = round_down_to_odd_price(table_ek_max * b2_factor_max)

        b_options[b2_vk_min_label] = b2_vk_min
        b_options[b2_vk_mid_label] = b2_vk_mid
        b_options[b2_vk_max_label] = b2_vk_max

        if st.session_state["b_selected_option"] not in b_options:
            st.session_state["b_selected_option"] = b2_vk_mid_label
        current_b_option = st.session_state["b_selected_option"]

        with method_right:
            b2_col1, b2_col2, b2_col3 = st.columns(3)
            with b2_col1:
                b_tab_min_active = current_b_option == b2_vk_min_label
                if st.button(
                    f"{'✓ ' if b_tab_min_active else ''}{format_eur(b2_vk_min)} ({format_eur_per_km(b2_vk_min, km)})",
                    key="b_pick_tab_min",
                    width="stretch",
                    type="primary" if b_tab_min_active else "secondary",
                ):
                    st.session_state["b_selected_option"] = b2_vk_min_label
                    st.rerun()
                st.caption(f"Richtwert-Basis: {format_eur(table_ek_min)}")
                st.caption(f"Richtwert Min x{str(b2_factor_min).replace('.', ',')}")
            with b2_col2:
                b_tab_mid_active = current_b_option == b2_vk_mid_label
                if st.button(
                    f"{'✓ ' if b_tab_mid_active else ''}{format_eur(b2_vk_mid)} ({format_eur_per_km(b2_vk_mid, km)})",
                    key="b_pick_tab_mid",
                    width="stretch",
                    type="primary" if b_tab_mid_active else "secondary",
                ):
                    st.session_state["b_selected_option"] = b2_vk_mid_label
                    st.rerun()
                st.caption(f"Richtwert-Basis: {format_eur(table_ek_mid)}")
                st.caption(f"Richtwert Mitte x{str(b2_factor_mid).replace('.', ',')}")
            with b2_col3:
                b_tab_max_active = current_b_option == b2_vk_max_label
                if st.button(
                    f"{'✓ ' if b_tab_max_active else ''}{format_eur(b2_vk_max)} ({format_eur_per_km(b2_vk_max, km)})",
                    key="b_pick_tab_max",
                    width="stretch",
                    type="primary" if b_tab_max_active else "secondary",
                ):
                    st.session_state["b_selected_option"] = b2_vk_max_label
                    st.rerun()
                st.caption(f"Richtwert-Basis: {format_eur(table_ek_max)}")
                st.caption(f"Richtwert Max x{str(b2_factor_max).replace('.', ',')}")

        b_selected_option = st.session_state["b_selected_option"]
        selected_vk_price = b_options[b_selected_option]
        expected_re_margin = selected_vk_price - ek_price
        expected_re_margin_pct = (
            (expected_re_margin / selected_vk_price) * 100 if selected_vk_price > 0 else 0.0
        )
        margin_label = (
            f"{format_eur(expected_re_margin)} ({expected_re_margin_pct:.1f} %)"
        )
        st.caption(f"Aktive Auswahl: {b_selected_option}")
        render_confidence_box(
            min(b_options.values()),
            max(b_options.values()),
            "B-Modell (alle Vorschläge)",
            expected_re_margin=expected_re_margin,
            compact=True,
            soft_warning=True,
            expected_re_margin_label=margin_label,
            show_hint=False,
        )

        if expected_re_margin < 0:
            st.error(
                "Diese Auswahl würde voraussichtlich einen Verlust verursachen. "
                "So bitte nicht anbieten."
            )
        elif expected_re_margin < 49.0:
            st.warning(
                "Achtung: Die erwartete RE-Marge dieser Auswahl ist niedrig. "
                "Preis bitte vor Angebotsfreigabe prüfen."
            )

    with st.container(border=True):
        st.markdown("### 4. Empfehlung")
        b_selected_option = st.session_state["b_selected_option"]
        selected_price = b_options[b_selected_option]
        render_recommendation_card(
            "Empfohlener Preis für das Angebot",
            selected_price,
            b_selected_option,
            f"Distanzklasse {distance_class} · EK {format_eur(ek_price)}",
            f"b_{b_selected_option.replace(' ', '_').replace(',', '').replace('-', '_').lower()}",
        )
        st.markdown("**Kurze Herleitung**")
        st.write(f"Distanzklasse bei {km:.1f} km: **{distance_class}**")
        st.write(
            "Genutzte Sätze (EUR/km): "
            f"min {rates['min']:.2f}, mittel {rates['mittel']:.2f}, max {rates['max']:.2f}"
        )
def main():
    st.set_page_config(page_title="Versandwerk Preisrechner [intern]", layout="wide")
    configure_app_logger()

    render_login_gate()
    render_app_header()
    render_user_session_bar()
    cfg_caption = None
    meta_col1, meta_col2 = st.columns([1.15, 1], gap="large")
    with meta_col1:
        st.caption("Interner MVP für Preisfindung: Direktfahrt und Paketversand")
    try:
        cfg_meta = load_parcel_config().get("meta", {})
        cfg_caption = (
            f"Tarifkonfiguration: v{cfg_meta.get('version', '-')}"
            + (f" | Stand: {cfg_meta.get('tariff_date')}" if cfg_meta.get("tariff_date") else "")
        )
    except Exception:
        cfg_caption = None
    with meta_col2:
        if cfg_caption:
            st.caption(cfg_caption)

    mode = st.radio(
        "Bitte Modus wählen",
        ["A - Selbst fahren", "B - Extern vergeben", "C - Paketversand Deutschland"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == "A - Selbst fahren":
        show_case_a()
    elif mode == "B - Extern vergeben":
        show_case_b()
    else:
        show_case_c()


if __name__ == "__main__":
    main()
