import streamlit as st
import streamlit.components.v1 as components


def format_eur(value):
    """Formatiert Zahlen als Euro mit 2 Nachkommastellen."""
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def format_eur_per_km(value, km):
    """Formatiert den resultierenden Preis pro km."""
    if km <= 0:
        return "- €/km (bei 0 km nicht berechenbar)"
    per_km = value / km
    return f"{per_km:,.2f} €/km".replace(",", "X").replace(".", ",").replace("X", ".")


def render_confidence_box(min_price, max_price, caption, expected_re_margin=None):
    """Zeigt Preis-Confidence auf Basis der Spanne."""
    span = max_price - min_price
    mid = (min_price + max_price) / 2 if (min_price + max_price) > 0 else 0
    span_pct = (span / mid * 100) if mid > 0 else 0

    if span_pct < 15:
        level = "Hoch"
        tone = "success"
        hint = "Preise liegen eng zusammen. Hohe Sicherheit."
    elif span_pct < 30:
        level = "Mittel"
        tone = "warning"
        hint = "Normale Streuung. Kurz plausibilisieren."
    elif span_pct < 50:
        level = "Niedrig"
        tone = "warning"
        hint = "Größere Streuung. Bitte kurz abstimmen."
    else:
        level = "Niedrig"
        tone = "error"
        hint = "Achtung - Preis bitte genau prüfen."

    st.markdown("**Preis-Confidence**")
    c1, c2, c3, c4 = st.columns(4)
    if expected_re_margin is not None:
        c1.metric("Erwartete RE-Marge", format_eur(expected_re_margin))
    c2.metric("Confidence", level)
    c3.metric("Spanne", format_eur(span))
    c4.metric("Relative Spanne", f"{span_pct:.1f} %")
    if tone == "success":
        st.success(f"{caption}: {hint}")
    elif tone == "warning":
        st.warning(f"{caption}: {hint}")
    else:
        st.error(f"{caption}: {hint}")


def render_case_c_recommendation(exp_result, lz48_result):
    """Zeigt C-spezifische Empfehlung statt generischer Confidence."""
    if exp_result is None and lz48_result is None:
        st.warning("Keine Paketoption möglich. Bitte anderen Transportmodus wählen.")
        return
    if exp_result is None:
        st.warning("Nur LZ48 ist möglich. EXP ist ausgeschlossen.")
        return
    if lz48_result is None:
        st.info("Nur EXP ist möglich. LZ48 ist ausgeschlossen.")
        return

    exp_price = exp_result["total"]
    lz48_price = lz48_result["total"]
    diff = abs(exp_price - lz48_price)
    ref = min(exp_price, lz48_price) if min(exp_price, lz48_price) > 0 else 1.0
    diff_pct = (diff / ref) * 100

    st.markdown("**Tarif-Empfehlung (C-Modell)**")
    r1, r2, r3 = st.columns(3)
    r1.metric("Preisunterschied", format_eur(diff))
    r2.metric("Relativer Unterschied", f"{diff_pct:.1f} %")
    cheaper = "EXP" if exp_price < lz48_price else "LZ48"
    r3.metric("Günstiger", cheaper)

    if lz48_price >= exp_price:
        st.error(
            "LZ48 ist nicht günstiger als EXP. Für den Kunden nur EXP aktiv anbieten."
        )
        return

    if diff_pct >= 25:
        st.success(
            "Großer Preisunterschied: beide Tarife aktiv anbieten (Kunde kann zwischen Preis und Service wählen)."
        )
    elif diff_pct <= 10:
        st.warning(
            "Niedriger Preisunterschied: LZ48 verliert als langsameres Produkt. EXP priorisiert anbieten."
        )
    else:
        st.info(
            "Mittlerer Preisunterschied: EXP als Standard nennen, LZ48 optional als Preisalternative erwähnen."
        )


def render_copy_text_button(label, text, key):
    """Zeigt einen Copy-Button fuer beliebigen Text."""
    js_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    components.html(
        f"""
        <div style="display:flex;gap:8px;align-items:center;font-family:'Source Sans Pro',sans-serif;">
            <span style="font-size:0.95rem;color:#333;">{label}</span>
            <button id="copy_text_btn_{key}" style="padding:6px 10px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer;font-family:'Source Sans Pro',sans-serif;font-size:0.95rem;">Text kopieren</button>
        </div>
        <script>
        const textBtn = document.getElementById("copy_text_btn_{key}");
        textBtn.addEventListener("click", async () => {{
            await navigator.clipboard.writeText("{js_text}");
            const oldText = textBtn.innerText;
            textBtn.innerText = "Kopiert";
            setTimeout(() => textBtn.innerText = oldText, 1200);
        }});
        </script>
        """,
        height=46,
    )


def _build_case_c_product_label(result):
    """Kundenfreundliche Produktbezeichnung fuer Modus C."""
    tariff_code = result.get("tariff_code", "")
    if tariff_code == "EXP":
        return "EXP - überNacht"
    if tariff_code == "LZ48":
        return "1-2 Tage Laufzeit - LZ48"
    return result.get("service_label", tariff_code)


def build_case_c_offer_text(result, alternative_result=None):
    """Erzeugt Angebots-Textbaustein fuer Modus C."""
    price_net = format_eur(result["total"]).replace(" €", "")
    main_product = _build_case_c_product_label(result)
    extra_labels = [name for name, amount in result["extras_breakdown"] if amount > 0]
    if result["late_fee"] > 0:
        extra_labels.append("Spätanmeldung")
    if result["late_pickup_fee"] > 0:
        extra_labels.append("Spätabholung")
    if result["insurance_fee"] > 0:
        extra_labels.append("Höherversicherung")
    service_suffix = f" ({'; '.join(extra_labels)})" if extra_labels else ""
    lines = [
        "Nochmals vielen Dank für Ihre Anfrage.",
        "",
        f"Versandart: {main_product}{service_suffix}",
        f"Preis: {price_net} EUR netto.",
    ]
    if alternative_result is not None:
        alt_price_net = format_eur(alternative_result["total"]).replace(" €", "")
        alt_product = _build_case_c_product_label(alternative_result)
        lines.append(f"Alternative: {alt_product}: {alt_price_net} EUR netto.")
    lines.extend(["", "Über eine Beauftragung würden wir uns sehr freuen."])
    return "\n".join(lines)


def build_case_c_price_rows(result):
    """Baut ein kompaktes Preisprotokoll mit allen Preisbausteinen."""
    rows = [("Basispreis", result["base_total"])]
    for name, amount in result["extras_breakdown"]:
        rows.append((f"Extra Service: {name}", amount))
    if result["late_fee"] > 0:
        rows.append((f"Spätanmeldung: {result['late_label']}", result["late_fee"]))
    if result["pickup_area_fee"] > 0:
        rows.append((f"Abholgebiet: {result['pickup_area_label']}", result["pickup_area_fee"]))
    if result["late_pickup_fee"] > 0:
        rows.append((f"Spätabholung: {result['late_pickup_label']}", result["late_pickup_fee"]))
    if result["oversize_fee"] > 0:
        rows.append(("Oversize-Zuschlag", result["oversize_fee"]))
    for label, amount in result["carrier_surcharge_breakdown"]:
        rows.append((f"Sonderzuschlag: {label}", amount))
    if result["insurance_fee"] > 0:
        rows.append(("Höherversicherung", result["insurance_fee"]))
    rows.append(("Gesamtpreis netto", result["total"]))
    return rows


def build_case_c_price_bullets(result):
    """Baut kopierbare Bullet-Points fuer Preisbausteine."""
    rows = build_case_c_price_rows(result)
    return "\n".join(f"- {name}: {format_eur(amount)}" for name, amount in rows)


def render_case_c_plausibility_checks(
    exp_reasons,
    lz48_reasons,
    needs_deku_check,
    island_service_selected,
    is_late_registration,
    is_late_pickup,
    insurance_enabled,
    declared_goods_value,
):
    """Zeigt operative Ampel-Checks vor dem Tarifvergleich."""
    st.markdown("### Plausibilitäts-Check")
    if exp_reasons and lz48_reasons:
        st.error("Beide Carrier sind aktuell ausgeschlossen. Kein Direktangebot senden.")
    elif exp_reasons or lz48_reasons:
        st.warning("Nur ein Carrier ist verfügbar. Ausschlussgründe prüfen, bevor versendet wird.")
    else:
        st.success("Beide Carrier sind technisch möglich.")

    if needs_deku_check or island_service_selected:
        st.warning("DeKu-Rücksprache erforderlich vor finaler Zusage.")
    if is_late_pickup and not is_late_registration:
        st.info("Spätabholung aktiv, aber keine Spätanmeldung: nur Spätabholung wird berechnet.")
    if insurance_enabled and declared_goods_value <= 250:
        st.info("Höherversicherung aktiviert, aber Warenwert <= 250 EUR: kein Zuschlag.")


def render_copy_price(label, value, key):
    """Zeigt empfohlenen Preis inkl. Copy-Button."""
    formatted = format_eur(value)
    formatted_net = formatted.replace(" €", "")
    offer_text = (
        "Nochmals vielen Dank für Ihre Anfrage.\n\n"
        f"Gerne bieten wir Ihnen an: {formatted_net} EUR netto.\n\n"
        "Über eine Beauftragung würden wir uns sehr freuen."
    )
    js_price = formatted.replace("\\", "\\\\").replace('"', '\\"')
    js_offer = offer_text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    st.markdown(f"**{label}: {formatted}**")
    components.html(
        f"""
        <div style="display:flex;gap:8px;align-items:center;">
            <button id="copy_btn_{key}" style="padding:8px 12px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer;">Preis kopieren</button>
            <button id="copy_text_btn_{key}" style="padding:8px 12px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer;">Text kopieren</button>
        </div>
        <script>
        const btn = document.getElementById("copy_btn_{key}");
        const textBtn = document.getElementById("copy_text_btn_{key}");
        btn.addEventListener("click", async () => {{
            await navigator.clipboard.writeText("{js_price}");
            const oldText = btn.innerText;
            btn.innerText = "Kopiert";
            setTimeout(() => btn.innerText = oldText, 1200);
        }});
        textBtn.addEventListener("click", async () => {{
            await navigator.clipboard.writeText("{js_offer}");
            const oldText = textBtn.innerText;
            textBtn.innerText = "Kopiert";
            setTimeout(() => textBtn.innerText = oldText, 1200);
        }});
        </script>
        """,
        height=52,
    )
    st.caption(offer_text)
    st.caption("Direkt nutzbar für Mail, Bamboo und Angebot.")
