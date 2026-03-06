import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# Zentrale Tabelle fuer B.2: Fahrzeugtyp -> Distanzklasse -> (min, mittel, max) in EUR/km
RATE_TABLE = {
    "Transporter / Sprinter": {
        "kurz": {"min": 1.10, "mittel": 1.30, "max": 1.50},
        "mittel": {"min": 0.80, "mittel": 1.10, "max": 1.40},
        "lang": {"min": 0.80, "mittel": 1.00, "max": 1.20},
    },
    "XXL / Planensprinter": {
        "kurz": {"min": 1.30, "mittel": 1.50, "max": 1.70},
        "mittel": {"min": 1.00, "mittel": 1.30, "max": 1.60},
        "lang": {"min": 1.10, "mittel": 1.20, "max": 1.40},
    },
    "7,5 to": {
        "kurz": {"min": 3.00, "mittel": 3.50, "max": 4.00},
        "mittel": {"min": 2.75, "mittel": 3.00, "max": 3.75},
        "lang": {"min": 2.00, "mittel": 2.50, "max": 3.00},
    },
    "12 to": {
        "kurz": {"min": 3.80, "mittel": 4.50, "max": 5.00},
        "mittel": {"min": 3.50, "mittel": 4.00, "max": 4.50},
        "lang": {"min": 2.80, "mittel": 3.20, "max": 3.80},
    },
}


def format_eur(value):
    """Formatiert Zahlen als Euro mit 2 Nachkommastellen."""
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def format_eur_per_km(value, km):
    """Formatiert den resultierenden Preis pro km."""
    if km <= 0:
        return "- €/km (bei 0 km nicht berechenbar)"
    per_km = value / km
    return (
        f"{per_km:,.2f} €/km".replace(",", "X").replace(".", ",").replace("X", ".")
    )


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
    js_offer = (
        offer_text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )

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
    st.caption("Direkt nutzbar fuer Mail, Bamboo und Angebot.")


def get_distance_class(km):
    """Ordnet die Distanzklasse gemaess MVP-Regeln zu."""
    if km < 100:
        return "kurz"
    if km <= 250:
        return "mittel"
    return "lang"


def calculate_case_a(km, one_way_minutes):
    """Berechnet dynamische Unter-/Obergrenze, Mittelwert und Gesamtminuten fuer Fall A."""
    price_a1 = 29 + (1.30 * km)
    total_minutes = (2 * one_way_minutes) + 30
    price_a2 = (total_minutes / 60) * 60

    lower_price = min(price_a1, price_a2)
    upper_price = max(price_a1, price_a2)
    price_mid = (lower_price + upper_price) / 2

    return lower_price, price_mid, upper_price, total_minutes, price_a1, price_a2


def calculate_case_b_ek(ek_price):
    """Berechnet die drei EK-basierten Verkaufspreise fuer Fall B.1."""
    return {
        "EK x 1,3": ek_price * 1.3,
        "EK x 1,4": ek_price * 1.4,
        "EK x 1,5": ek_price * 1.5,
    }


def calculate_case_b_table(km, vehicle_type):
    """Berechnet Distanzklasse, Satzwerte und Preise fuer Fall B.2."""
    distance_class = get_distance_class(km)
    rates = RATE_TABLE[vehicle_type][distance_class]
    prices = {
        "Tabellen-Min": km * rates["min"],
        "Tabellen-Mittel": km * rates["mittel"],
        "Tabellen-Max": km * rates["max"],
    }
    return distance_class, rates, prices


def show_case_a():
    st.subheader("A - Selbst fahren")

    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        km = st.number_input("Kilometer", min_value=0.0, value=100.0, step=1.0)
    with col2:
        one_way_minutes = st.number_input(
            "Fahrtdauer einfach (Minuten)", min_value=0, value=90, step=1
        )

    (
        lower_price,
        price_mid,
        upper_price,
        total_minutes,
        price_a1,
        price_a2,
    ) = calculate_case_a(km, one_way_minutes)

    st.markdown("### VK-Vorschläge")
    st.info("Alle folgenden Werte sind VK-Vorschläge (Verkaufspreise) für den Kunden.")

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

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Untergrenze (VK)", format_eur(lower_price))
        st.caption(format_eur_per_km(lower_price, km))
        st.caption(lower_source)
    with c2:
        st.metric("Mittelwert (VK)", format_eur(price_mid))
        st.caption(format_eur_per_km(price_mid, km))
        st.caption(mid_source)
    with c3:
        st.metric("Obergrenze (VK)", format_eur(upper_price))
        st.caption(format_eur_per_km(upper_price, km))
        st.caption(upper_source)

    st.markdown("**Preis fuer Angebot auswaehlen**")
    if "a_selected_option" not in st.session_state:
        st.session_state["a_selected_option"] = "Mittelwert"

    s1, s2, s3 = st.columns(3)
    with s1:
        if st.button("Untergrenze", key="a_pick_lower", use_container_width=True):
            st.session_state["a_selected_option"] = "Untergrenze"
        st.caption(lower_source)
    with s2:
        if st.button("Mittelwert", key="a_pick_mid", use_container_width=True):
            st.session_state["a_selected_option"] = "Mittelwert"
        st.caption(mid_source)
    with s3:
        if st.button("Obergrenze", key="a_pick_upper", use_container_width=True):
            st.session_state["a_selected_option"] = "Obergrenze"
        st.caption(upper_source)

    selected_option = st.session_state["a_selected_option"]
    selected_prices = {
        "Untergrenze": lower_price,
        "Mittelwert": price_mid,
        "Obergrenze": upper_price,
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

    st.caption(
        f"Aktive Auswahl: {selected_option} ({selected_sources[selected_option]})"
    )
    render_copy_price(
        "Empfohlener Preis",
        selected_prices[selected_option],
        f"a_{selected_key[selected_option]}",
    )

    st.markdown("**Kurze Herleitung**")
    st.write(
        f"A.1 Formel: 29,00 € + (1,30 € x {km:.1f} km) = {format_eur(price_a1)}"
    )
    st.write(
        "A.2 Formel: "
        f"(2 x {one_way_minutes} min + 30 min) = {total_minutes:.0f} min, "
        f"das entspricht {total_minutes / 60:.2f} h x 60 € = {format_eur(price_a2)}"
    )
    st.write(
        f"Dynamische Sortierung: Untergrenze = {format_eur(lower_price)}, "
        f"Obergrenze = {format_eur(upper_price)}"
    )

    chart_df = pd.DataFrame(
        {
            "Preispunkt": ["Untergrenze", "Mittelwert", "Obergrenze"],
            "Preis": [lower_price, price_mid, upper_price],
        }
    ).set_index("Preispunkt")

    st.markdown("**Visualisierung**")
    st.bar_chart(chart_df)


def show_case_b():
    st.subheader("B - Extern vergeben")

    col1, col2, col3, _ = st.columns([1, 1.4, 1, 1.2])
    with col1:
        km = st.number_input("Kilometer", min_value=0.0, value=150.0, step=1.0, key="b_km")
    with col2:
        vehicle_type = st.selectbox("Fahrzeugtyp", list(RATE_TABLE.keys()))
    with col3:
        ek_price = st.number_input(
            "Einkaufspreis (EK)", min_value=0.0, value=200.0, step=1.0
        )

    ek_prices = calculate_case_b_ek(ek_price)
    distance_class, rates, table_prices = calculate_case_b_table(km, vehicle_type)

    st.markdown("### VK-Vorschläge")
    st.info("Alle folgenden Werte sind VK-Vorschläge (Verkaufspreise) für den Kunden.")

    st.markdown("**B.1 EK-basierte VK-Vorschlaege**")
    b1_col1, b1_col2, b1_col3 = st.columns(3)
    with b1_col1:
        st.metric("EK x 1,3 (VK)", format_eur(ek_prices["EK x 1,3"]))
        st.caption(format_eur_per_km(ek_prices["EK x 1,3"], km))
    with b1_col2:
        st.metric("EK x 1,4 (VK)", format_eur(ek_prices["EK x 1,4"]))
        st.caption(format_eur_per_km(ek_prices["EK x 1,4"], km))
    with b1_col3:
        st.metric("EK x 1,5 (VK)", format_eur(ek_prices["EK x 1,5"]))
        st.caption(format_eur_per_km(ek_prices["EK x 1,5"], km))

    st.markdown("**B.2 Tabellen-VK-Richtwerte**")
    b2_col1, b2_col2, b2_col3 = st.columns(3)
    with b2_col1:
        st.metric("Tabellen-Min (VK)", format_eur(table_prices["Tabellen-Min"]))
        st.caption(format_eur_per_km(table_prices["Tabellen-Min"], km))
    with b2_col2:
        st.metric("Tabellen-Mittel (VK)", format_eur(table_prices["Tabellen-Mittel"]))
        st.caption(format_eur_per_km(table_prices["Tabellen-Mittel"], km))
    with b2_col3:
        st.metric("Tabellen-Max (VK)", format_eur(table_prices["Tabellen-Max"]))
        st.caption(format_eur_per_km(table_prices["Tabellen-Max"], km))

    st.markdown("**Preis fuer Angebot auswaehlen (B.2 Tabelle)**")
    if "b_selected_option" not in st.session_state:
        st.session_state["b_selected_option"] = "Tabellen-Mittel"

    t1, t2, t3 = st.columns(3)
    with t1:
        if st.button("Tabellen-Min", key="b_pick_min", use_container_width=True):
            st.session_state["b_selected_option"] = "Tabellen-Min"
    with t2:
        if st.button("Tabellen-Mittel", key="b_pick_mid", use_container_width=True):
            st.session_state["b_selected_option"] = "Tabellen-Mittel"
    with t3:
        if st.button("Tabellen-Max", key="b_pick_max", use_container_width=True):
            st.session_state["b_selected_option"] = "Tabellen-Max"

    b_selected_option = st.session_state["b_selected_option"]
    b_selected_key = {
        "Tabellen-Min": "min",
        "Tabellen-Mittel": "mid",
        "Tabellen-Max": "max",
    }
    st.caption(f"Aktive Auswahl: {b_selected_option}")
    render_copy_price(
        "Empfohlener Preis",
        table_prices[b_selected_option],
        f"b_tab_{b_selected_key[b_selected_option]}",
    )

    st.markdown("**Kurze Herleitung**")
    st.write(f"Distanzklasse bei {km:.1f} km: **{distance_class}**")
    st.write(
        "Genutzte Saetze (EUR/km): "
        f"min {rates['min']:.2f}, mittel {rates['mittel']:.2f}, max {rates['max']:.2f}"
    )

    chart_df = pd.DataFrame(
        {
            "EK-basiert": [
                ek_prices["EK x 1,3"],
                ek_prices["EK x 1,4"],
                ek_prices["EK x 1,5"],
            ],
            "Tabelle": [
                table_prices["Tabellen-Min"],
                table_prices["Tabellen-Mittel"],
                table_prices["Tabellen-Max"],
            ],
        },
        index=["Min", "Mittel", "Max"],
    )

    st.markdown("**Vergleichsvisualisierung**")
    st.bar_chart(chart_df)


def main():
    st.set_page_config(page_title="Versandwerk Direktfahrt-Rechner", layout="wide")

    st.title("Versandwerk Direktfahrt-Rechner")
    st.caption("Interner MVP fuer die Preisfindung bei Direktfahrten")

    mode = st.radio(
        "Bitte Modus waehlen",
        ["A - Selbst fahren", "B - Extern vergeben"],
        horizontal=True,
    )

    st.divider()

    if mode == "A - Selbst fahren":
        show_case_a()
    else:
        show_case_b()


if __name__ == "__main__":
    main()
