import html

import streamlit as st
import streamlit.components.v1 as components


def render_app_styles():
    """Inject a small, targeted style layer for spacing and visual hierarchy."""
    st.markdown(
        """
        <style>
        :root {
            --vw-accent: #e84328;
            --vw-accent-soft: #b5d6b2;
        }

        .block-container {
            max-width: 96rem;
            padding-top: 1rem;
            padding-right: 1.6rem;
            padding-bottom: 1.4rem;
            padding-left: 1.6rem;
        }

        div[data-testid="stAlert"] {
            border-radius: 12px;
        }

        div[data-testid="stMetric"] {
            background: rgba(181, 214, 178, 0.14);
            border: 1px solid rgba(181, 214, 178, 0.48);
            border-radius: 14px;
            padding: 0.55rem 0.75rem;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.45rem;
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            background-color: var(--vw-accent);
            border-color: var(--vw-accent);
        }

        div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: #cf381e;
            border-color: #cf381e;
        }

        div[data-testid="stExpander"] {
            border-radius: 14px;
        }

        .vw-reco-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(249,250,251,0.98) 100%);
            border: 1px solid rgba(19, 31, 53, 0.08);
            border-radius: 20px;
            padding: 1rem 1rem 0.9rem 1rem;
            box-shadow: 0 18px 38px rgba(19, 31, 53, 0.08);
            margin-bottom: 0.65rem;
        }

        .vw-reco-card--muted {
            background: linear-gradient(180deg, rgba(251,252,252,0.98) 0%, rgba(247,248,249,0.98) 100%);
            border-color: rgba(19, 31, 53, 0.06);
            box-shadow: 0 10px 24px rgba(19, 31, 53, 0.05);
        }

        .vw-reco-card--muted .vw-reco-price,
        .vw-reco-card--muted .vw-reco-meta-value {
            color: #304258;
        }

        .vw-reco-card--muted .vw-reco-subline,
        .vw-reco-card--muted .vw-reco-meta-detail {
            color: #758193;
        }

        .vw-reco-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(29, 111, 95, 0.10);
            color: #17584c;
            border: 1px solid rgba(29, 111, 95, 0.18);
            border-radius: 999px;
            padding: 0.28rem 0.7rem;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.01em;
        }

        .vw-reco-kicker {
            margin-top: 0.9rem;
            color: #5f6b7a;
            font-size: 0.82rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .vw-reco-price {
            margin-top: 0.15rem;
            color: #13213a;
            font-size: clamp(2.2rem, 4vw, 3rem);
            line-height: 1.05;
            font-weight: 800;
            letter-spacing: -0.03em;
        }

        .vw-reco-subline {
            margin-top: 0.35rem;
            color: #6b7280;
            font-size: 0.92rem;
        }

        .vw-reco-meta {
            margin-top: 1rem;
            padding: 0.85rem 0.95rem;
            background: rgba(19, 31, 53, 0.04);
            border: 1px solid rgba(19, 31, 53, 0.06);
            border-radius: 14px;
        }

        .vw-reco-meta-label {
            color: #6b7280;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .vw-reco-meta-value {
            margin-top: 0.22rem;
            color: #13213a;
            font-size: 1rem;
            font-weight: 700;
        }

        .vw-reco-meta-detail {
            margin-top: 0.2rem;
            color: #6b7280;
            font-size: 0.88rem;
            line-height: 1.35;
        }

        .vw-casec-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.8rem;
            margin-bottom: 0.7rem;
        }

        .vw-casec-head-main {
            min-width: 0;
        }

        .vw-casec-carrier {
            color: #13213a;
            font-size: 1.18rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .vw-casec-service {
            margin-top: 0.24rem;
            color: #6b7280;
            font-size: 0.92rem;
            line-height: 1.35;
        }

        .vw-casec-status {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            white-space: nowrap;
            background: rgba(29, 111, 95, 0.10);
            color: #17584c;
            border: 1px solid rgba(29, 111, 95, 0.18);
            border-radius: 999px;
            padding: 0.28rem 0.72rem;
            font-size: 0.82rem;
            font-weight: 700;
        }

        .vw-casec-status--muted {
            background: rgba(19, 31, 53, 0.05);
            color: #4d5a6d;
            border-color: rgba(19, 31, 53, 0.10);
        }

        .vw-casec-note {
            margin: 0.15rem 0 0.85rem 0;
            color: #6b7280;
            font-size: 0.88rem;
            line-height: 1.35;
        }

        </style>
        <script>
        (() => {
            const replaceEnterHint = () => {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                const targets = [];
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    if (node.nodeValue && node.nodeValue.includes("Press enter to apply")) {
                        targets.push(node);
                    }
                }
                targets.forEach((node) => {
                    node.nodeValue = node.nodeValue.replaceAll(
                        "Press enter to apply",
                        "Mit Enter best?tigen"
                    );
                });
            };

            replaceEnterHint();
            const observer = new MutationObserver(() => replaceEnterHint());
            observer.observe(document.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def format_eur(value):
    """Formatiert Zahlen als Euro mit 2 Nachkommastellen."""
    return f"{value:,.2f} \u20ac".replace(",", "X").replace(".", ",").replace("X", ".")


def format_eur_text(value):
    """Formatiert Zahlen konsistent als EUR-Text."""
    return f"{value:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def format_eur_per_km(value, km):
    """Formatiert den resultierenden Preis pro km."""
    if km <= 0:
        return "- EUR/km (bei 0 km nicht berechenbar)"
    per_km = value / km
    return f"{per_km:,.2f} EUR/km".replace(",", "X").replace(".", ",").replace("X", ".")


def render_confidence_box(min_price, max_price, caption, expected_re_margin=None):
    """Zeigt Preiskonfidenz auf Basis der Spanne."""
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
        hint = "Groessere Streuung. Bitte kurz abstimmen."
    else:
        level = "Niedrig"
        tone = "error"
        hint = "Achtung - Preis bitte genau pruefen."

    st.markdown("**Preiskonfidenz**")
    if expected_re_margin is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Erwartete RE-Marge", format_eur(expected_re_margin))
        c2.metric("Konfidenz", level)
        c3.metric("Spanne", format_eur(span))
        c4.metric("Relative Spanne", f"{span_pct:.1f} %")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Konfidenz", level)
        c2.metric("Spanne", format_eur(span))
        c3.metric("Relative Spanne", f"{span_pct:.1f} %")
    if tone == "success":
        st.success(f"{caption}: {hint}")
    elif tone == "warning":
        st.warning(f"{caption}: {hint}")
    else:
        st.error(f"{caption}: {hint}")


def render_case_c_recommendation(exp_result, lz48_result):
    """Zeigt C-spezifische Empfehlung statt generischer Confidence."""
    if exp_result is None and lz48_result is None:
        st.warning("Keine Paketoption moeglich. Bitte anderen Transportmodus waehlen.")
        return
    if exp_result is None:
        st.warning("Nur LZ48 ist moeglich. EXP ist ausgeschlossen.")
        return
    if lz48_result is None:
        st.info("Nur EXP ist moeglich. LZ48 ist ausgeschlossen.")
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
    r3.metric("Guenstiger", cheaper)

    if lz48_price >= exp_price:
        st.error(
            "LZ48 ist nicht guenstiger als EXP. Fuer den Kunden nur EXP aktiv anbieten."
        )
        return

    if diff_pct >= 25:
        st.success(
            "Grosser Preisunterschied: beide Tarife aktiv anbieten (Kunde kann zwischen Preis und Service waehlen)."
        )
    elif diff_pct <= 10:
        st.warning(
            "Niedriger Preisunterschied: LZ48 verliert als langsameres Produkt. EXP priorisiert anbieten."
        )
    else:
        st.info(
            "Mittlerer Preisunterschied: EXP als Standard nennen, LZ48 optional als Preisalternative erwaehnen."
        )


def render_copy_text_button(label, text, key):
    """Zeigt einen Copy-Button \u00fcr beliebigen Text."""
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


def render_case_c_carrier_header(carrier_label, service_label, carrier_code, status_label, muted=False):
    """Rendert einen kompakten Carrier-Kopf mit Status-Badge."""
    carrier_html = html.escape(carrier_label, quote=False)
    service_html = html.escape(
        f"Tarif: {service_label} (intern: {carrier_code})",
        quote=False,
    )
    status_html = html.escape(status_label, quote=False)
    status_class = "vw-casec-status vw-casec-status--muted" if muted else "vw-casec-status"
    st.markdown(
        f"""
        <div class="vw-casec-head">
            <div class="vw-casec-head-main">
                <div class="vw-casec-carrier">{carrier_html}</div>
                <div class="vw-casec-service">{service_html}</div>
            </div>
            <div class="{status_class}">{status_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_case_c_product_label(result):
    """Kundenfreundliche Produktbezeichnung \u00fcr Modus C."""
    tariff_code = result.get("tariff_code", "")
    if tariff_code == "EXP":
        return "EXP - \u00fcberNacht"
    if tariff_code == "LZ48":
        return "1-2 Tage Laufzeit - LZ48"
    return result.get("service_label", tariff_code)


def build_case_c_offer_text(result, alternative_result=None):
    """Erzeugt Angebots-Textbaustein \u00fcr Modus C."""
    price_net = format_eur_text(result["total"])
    main_product = _build_case_c_product_label(result)
    extra_labels = [name for name, amount in result["extras_breakdown"] if amount > 0]
    if result["late_fee"] > 0:
        extra_labels.append("Spaetanmeldung")
    if result["late_pickup_fee"] > 0:
        extra_labels.append("Spaetabholung")
    if result["insurance_fee"] > 0:
        extra_labels.append("Hoeherversicherung")
    service_suffix = f" ({'; '.join(extra_labels)})" if extra_labels else ""
    lines = [
        "Nochmals vielen Dank \u00fcr Ihre Anfrage.",
        "",
        f"Versandart: {main_product}{service_suffix}",
        f"Preis: {price_net} netto.",
    ]
    if alternative_result is not None:
        alt_price_net = format_eur_text(alternative_result["total"])
        alt_product = _build_case_c_product_label(alternative_result)
        lines.append(f"Alternative: {alt_product}: {alt_price_net} netto.")
    lines.extend(["", "\u00dcber eine Beauftragung w\u00fcrden wir uns sehr freuen."])
    return "\n".join(lines)


def build_case_c_price_rows(result):
    """Baut ein kompaktes Preisprotokoll mit allen Preisbausteinen."""
    rows = [("Basispreis", result["base_total"])]
    for name, amount in result["extras_breakdown"]:
        rows.append((f"Extra Service: {name}", amount))
    if result["late_fee"] > 0:
        rows.append((f"Spaetanmeldung: {result['late_label']}", result["late_fee"]))
    if result["pickup_area_fee"] > 0:
        rows.append((f"Abholgebiet: {result['pickup_area_label']}", result["pickup_area_fee"]))
    if result["late_pickup_fee"] > 0:
        rows.append((f"Spaetabholung: {result['late_pickup_label']}", result["late_pickup_fee"]))
    if result["oversize_fee"] > 0:
        rows.append(("Oversize-Zuschlag", result["oversize_fee"]))
    for label, amount in result["carrier_surcharge_breakdown"]:
        rows.append((f"Sonderzuschlag: {label}", amount))
    if result["insurance_fee"] > 0:
        rows.append(("Hoeherversicherung", result["insurance_fee"]))
    rows.append(("Gesamtpreis netto", result["total"]))
    return rows


def build_case_c_price_bullets(result):
    """Baut kopierbare Bullet-Points \u00fcr Preisbausteine."""
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
    st.markdown("### Plausibilitaets-Check")
    if exp_reasons and lz48_reasons:
        st.error("Beide Carrier sind aktuell ausgeschlossen. Kein Direktangebot senden.")
    elif exp_reasons or lz48_reasons:
        st.warning("Nur ein Carrier ist verfuegbar. Ausschlussgruende pruefen, bevor versendet wird.")
    else:
        st.success("Beide Carrier sind technisch moeglich.")

    if needs_deku_check or island_service_selected:
        st.warning("DeKu-Ruecksprache erforderlich vor finaler Zusage.")
    if is_late_pickup and not is_late_registration:
        st.info("Spaetabholung aktiv, aber keine Spaetanmeldung: nur Spaetabholung wird berechnet.")
    if insurance_enabled and declared_goods_value <= 250:
        st.info("Hoeherversicherung aktiviert, aber Warenwert <= 250 EUR: kein Zuschlag.")


def render_copy_price(label, value, key, show_offer_text=True):
    """Zeigt empfohlenen Preis inkl. Copy-Button."""
    copy_text = (
        "Nochmals vielen Dank f\u00fcr Ihre Anfrage.\n\n"
        f"Gerne bieten wir Ihnen an: {format_eur_text(value)} netto.\n\n"
        "\u00dcber eine Beauftragung w\u00fcrden wir uns sehr freuen."
    )
    render_recommendation_card(
        status_label=label,
        value=value,
        selection_label="Aktive Auswahl",
        selection_detail="Direkt als Angebotspreis verwendbar",
        key=key,
        copy_text=copy_text,
        subline="Direkt als Angebotspreis verwendbar",
        action_hint="Preis oder Angebotstext direkt kopierbar",
    )
    if show_offer_text:
        st.caption(copy_text)
        st.caption("Direkt nutzbar f\u00fcr Mail, Bamboo und Angebot.")


def render_recommendation_card(
    status_label,
    value,
    selection_label,
    selection_detail,
    key,
    copy_text=None,
    subline="Direkt als Angebotspreis verwendbar",
    action_hint="Preis oder Angebotstext direkt kopierbar",
    muted=False,
):
    """Render a premium recommendation card with dominant price and copy actions."""
    formatted = format_eur(value)
    formatted_text = format_eur_text(value)
    if copy_text is None:
        copy_text = (
            "Nochmals vielen Dank f\u00fcr Ihre Anfrage.\n\n"
            f"Gerne bieten wir Ihnen an: {formatted_text} netto.\n\n"
            "\u00dcber eine Beauftragung w\u00fcrden wir uns sehr freuen."
        )

    js_price = formatted.replace("\\", "\\\\").replace('"', '\\"')
    js_offer = copy_text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    title_offer = html.escape(copy_text, quote=True).replace("\n", "&#10;")
    selection_label_html = html.escape(selection_label, quote=False)
    selection_detail_html = html.escape(selection_detail, quote=False)
    status_label_html = html.escape(status_label, quote=False)
    formatted_html = html.escape(formatted, quote=False)
    subline_html = html.escape(subline, quote=False)
    action_hint_html = html.escape(action_hint, quote=False)
    card_class = "vw-reco-card vw-reco-card--muted" if muted else "vw-reco-card"

    st.markdown(
        f"""
        <div class="{card_class}">
            <div class="vw-reco-badge">{status_label_html}</div>
            <div class="vw-reco-kicker">Aktuell empfohlen</div>
            <div class="vw-reco-price">{formatted_html}</div>
            <div class="vw-reco-subline">{subline_html}</div>
            <div class="vw-reco-meta">
                <div class="vw-reco-meta-label">Basis</div>
                <div class="vw-reco-meta-value">{selection_label_html}</div>
                <div class="vw-reco-meta-detail">{selection_detail_html}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    components.html(
        f"""
        <div style="font-family:'Source Sans Pro',sans-serif;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:stretch;margin-top:2px;">
                <button id="copy_btn_{key}" style="padding:10px 12px;border:1px solid rgba(19,31,53,0.12);border-radius:12px;background:#ffffff;cursor:pointer;font-weight:600;min-height:44px;font-family:'Source Sans Pro',sans-serif;">Preis kopieren</button>
                <button id="copy_text_btn_{key}" title="{title_offer}" style="padding:10px 12px;border:1px solid rgba(19,31,53,0.12);border-radius:12px;background:#ffffff;cursor:pointer;font-weight:600;min-height:44px;font-family:'Source Sans Pro',sans-serif;">Text kopieren</button>
            </div>
            <div style="margin-top:8px;color:#6b7280;font-size:0.84rem;font-family:'Source Sans Pro',sans-serif;">{action_hint_html}</div>
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
        height=104,
    )


def render_icon_toggle(label, key, help_text, icon_path=None, icon_width=42, on_change=None):
    """Render a compact inline icon-toggle-help group."""
    icon_col, toggle_col = st.columns([0.16, 0.84], gap="small", vertical_alignment="center")
    with icon_col:
        if icon_path:
            st.image(icon_path, width=icon_width)
    with toggle_col:
        return st.toggle(label, key=key, help=help_text, on_change=on_change)
