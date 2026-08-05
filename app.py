import streamlit as st
import pandas as pd
from datetime import date

# ==========================================
# KONFIGURACJA STRONY
# ==========================================
st.set_page_config(
    page_title="Kalkulator Tras i Kosztów Floty",
    page_icon="🚚",
    layout="wide"
)

# ==========================================
# SYSTEM LOGOWANIA DO APLIKACJI
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔐 Logowanie do Kalkulatora Floty")
    st.caption("Aplikacja do rozliczania tras Amazon + UTA")
    
    password = st.text_input("Wpisz hasło dostępu:", type="password")
    
    if st.button("Zaloguj się", type="primary"):
        if password == "biuro2026":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Nieprawidłowe hasło!")
    return False

if not check_password():
    st.stop()

# ==========================================
# INTERFEJS GŁÓWNY
# ==========================================
st.title("🚚 Kalkulator Kosztów i Zysku Tras")
st.caption("Rozliczenie tras Amazon Relay + Koszty UTA / Drogowe")

st.sidebar.header("⚙️ Ustawienia i dane trasy")

# 1. LISTA POJAZDÓW FLOTY
# TUTAJ MOŻESZ DOPISAĆ WIĘCEJ SWOICH REJESTRACJI DO LISTY:
FLOTA_VEHICLES = ["KN 0782G", "Wpisz inny numer..."]

vehicle_choice = st.sidebar.selectbox("🚛 Wybierz pojazd z floty", options=FLOTA_VEHICLES)

if vehicle_choice == "Wpisz inny numer...":
    selected_plate = st.sidebar.text_input("Wpisz numer rejestracyjny", value="KN 0782G").strip().upper()
else:
    selected_plate = vehicle_choice

# 2. DATY I KOSZTY STAŁE
col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("Data od", value=date(2026, 6, 23))
end_date = col_d2.date_input("Data do", value=date(2026, 6, 28))

daily_fixed_cost = st.sidebar.number_input("💵 Koszt stały auta (PLN / dzień)", value=1140.0, step=10.0)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Dystans i Paliwo")
manual_km = st.sidebar.number_input("🗺️ Przebieg km (z bloku Amazon / Ruptela)", value=4415.8, step=10.0)
manual_liters = st.sidebar.number_input("⛽ Zużyte paliwo (Litry)", value=0.0, step=10.0)

# 3. STAWKA AMAZON
with st.sidebar.expander("📦 Stawka za Blok Amazon (€)", expanded=True):
    amazon_rate_eur = st.number_input("Stawka za blok w EUR (€)", value=4942.40, step=100.0)
    rate_amazon_eur = st.number_input("Kurs EUR dla stawki (EUR -> PLN)", value=4.31, step=0.01)

# 4. KOSZTY UTA / OPŁATY DROGOWE
with st.sidebar.expander("💳 Wydatki z UTA / Drogowe", expanded=True):
    cost_pln = st.number_input("Kwota w PLN", value=0.0, step=50.0)
    cost_eur = st.number_input("Kwota w EUR (€)", value=0.0, step=50.0)
    cost_czk = st.number_input("Kwota w CZK (KORONY)", value=0.0, step=100.0)
    
    st.markdown("---")
    rate_costs_eur = st.number_input("Kurs EUR do kosztów -> PLN", value=4.30, step=0.01)
    rate_czk = st.number_input("Kurs CZK -> PLN", value=0.17, step=0.01)

calculate_btn = st.sidebar.button("🚀 Przelicz koszty i zysk", type="primary", use_container_width=True)

# ==========================================
# OBLICZENIA I WYNIKI
# ==========================================
if calculate_btn or True:  # Liczy od razu domyślnie
    if start_date > end_date:
        st.error("⚠️ Data początkowa nie może być późniejsza niż końcowa!")
    else:
        final_km = manual_km if manual_km > 0 else 1.0

        amazon_rate_pln = amazon_rate_eur * rate_amazon_eur
        cost_eur_in_pln = cost_eur * rate_costs_eur
        cost_czk_in_pln = cost_czk * rate_czk
        total_uta_pln = cost_pln + cost_eur_in_pln + cost_czk_in_pln

        num_days = (end_date - start_date).days + 1
        total_fixed = num_days * daily_fixed_cost
        total_cost_pln = total_fixed + total_uta_pln
        
        profit_pln = amazon_rate_pln - total_cost_pln
        profit_eur = profit_pln / rate_amazon_eur if rate_amazon_eur > 0 else 0.0
        margin = (profit_pln / amazon_rate_pln * 100) if amazon_rate_pln > 0 else 0.0
        
        cost_per_km_pln = round(total_cost_pln / final_km, 2)
        earnings_per_km_eur = round(amazon_rate_eur / final_km, 2)
        earnings_per_km_pln = round(amazon_rate_pln / final_km, 2)

        st.markdown("---")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Stawka Amazon", f"{amazon_rate_eur:.2f} €", delta=f"{amazon_rate_pln:.2f} PLN")
        m2.metric("Łączne Koszty", f"{total_cost_pln:.2f} PLN")
        m3.metric("CZYSTY ZYSK", f"{profit_pln:.2f} PLN", delta=f"{profit_eur:.2f} € ({margin:.1f}%)")
        m4.metric("Stawka / km", f"{earnings_per_km_eur:.2f} €/km", delta=f"{earnings_per_km_pln:.2f} PLN/km")
        m5.metric("Koszt / km", f"{cost_per_km_pln:.2f} PLN/km")

        st.markdown("---")

        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("📊 Podsumowanie Finansowe (PLN)")
            summary_data = {
                "Kategoria": [
                    f"Stawka Amazon ({amazon_rate_eur:.2f} € @ {rate_amazon_eur} PLN)",
                    "Wydatki UTA w PLN", 
                    f"Wydatki UTA w EUR ({cost_eur:.2f} €)", 
                    f"Wydatki UTA w CZK ({cost_czk:.2f} CZK)", 
                    "Koszty stałe auta", 
                    "SUMA KOSZTÓW",
                    "CZYSTY ZYSK (PLN)",
                    "CZYSTY ZYSK (EUR)"
                ],
                "Kwota": [
                    f"{amazon_rate_pln:.2f} PLN",
                    f"{cost_pln:.2f} PLN", 
                    f"{cost_eur_in_pln:.2f} PLN", 
                    f"{cost_czk_in_pln:.2f} PLN", 
                    f"{total_fixed:.2f} PLN", 
                    f"{total_cost_pln:.2f} PLN",
                    f"{profit_pln:.2f} PLN",
                    f"{profit_eur:.2f} €"
                ],
            }
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

        with col_right:
            st.subheader("⛽ Statystyki Trasy")
            st.write(f"- **Pojazd:** {selected_plate}")
            st.write(f"- **Dystans trasy:** {final_km:.1f} km")
            st.write(f"- **Dni w trasie:** {num_days} dni (koszt stały {daily_fixed_cost} PLN/dzień)")
            st.write(f"- **Kurs EUR Amazon:** {rate_amazon_eur} PLN")
