import streamlit as st
import pandas as pd
from datetime import date, timedelta
import requests
from typing import Dict, Any

# ==========================================
# KONFIGURACJA STRONY
# ==========================================
st.set_page_config(
    page_title="Kalkulator Tras i Kosztów Floty",
    page_icon="🚚",
    layout="wide"
)

# ==========================================
# SYSTEM LOGOWANIA / HASŁO
# ==========================================
def check_password():
    """Zabezpieczenie aplikacji prostym hasłem."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔐 Logowanie do Kalkulatora Floty")
    st.caption("Aplikacja do rozliczania tras (Ruptela + UTA + Amazon)")
    
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
# 1. MODUŁ RUPTELA API
# ==========================================
class RuptelaAPI:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def get_trip_distance(self, vehicle_plate: str, start_date: date, end_date: date) -> float:
        if not self.api_key:
            return 0.0

        headers = {"Authorization": f"Bearer {self.api_key}"}
        endpoint = f"{self.base_url}/v1/reports/trips"
        params = {
            "plate_number": vehicle_plate,
            "from": f"{start_date}T00:00:00Z",
            "to": f"{end_date}T23:59:59Z"
        }
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                report_data = response.json()
                total_distance_m = sum(trip.get("distance", 0) for trip in report_data.get("trips", []))
                return round(total_distance_m / 1000.0, 2)
        except Exception:
            pass
        return 0.0

# ==========================================
# INTERFEJS GŁÓWNY
# ==========================================
st.title("🚚 Kalkulator Kosztów i Zysku Tras (Ruptela + Amazon)")
st.caption("Aplikacja do automatycznego rozliczania tras, wydatków z UTA oraz rentowności bloków.")

st.sidebar.header("⚙️ Ustawienia i dane wejściowe")

# API KEY RUPTELA
with st.sidebar.expander("🔑 Klucz Ruptela API"):
    ruptela_api_key = st.text_input("Podaj Klucz API (API Key)", type="password", value="", help="Wklej klucz dostępowy do API Ruptela")

vehicle_plate = st.sidebar.text_input("🚛 Numer rejestracyjny pojazdu", value="KN0782G").strip().upper()

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("Data od", value=date.today() - timedelta(days=7))
end_date = col_d2.date_input("Data do", value=date.today())

daily_fixed_cost = st.sidebar.number_input("💵 Koszt stały auta (PLN / dzień)", value=180.0, step=10.0)
manual_km = st.sidebar.number_input("🗺️ Przebieg km (jeśli brak połączenia API)", value=0.0, step=50.0)

# ==========================================
# STAWKA AMAZON W EUR
# ==========================================
with st.sidebar.expander("📦 Stawka za Blok Amazon (€)", expanded=True):
    amazon_rate_eur = st.number_input("Stawka za blok w EUR (€)", value=2800.0, step=100.0, help="Fracht EUR za blok Amazon")
    rate_amazon_eur = st.number_input("Kurs EUR dla stawki (EUR -> PLN)", value=4.25, step=0.01)

# ==========================================
# FORMULARZ KOSZTÓW UTA
# ==========================================
with st.sidebar.expander("💳 Wydatki z UTA (Ręcznie)", expanded=False):
    st.markdown("**Wpisz kwoty w poszczególnych walutach:**")
    cost_pln = st.number_input("Kwota w PLN", value=0.0, step=50.0)
    cost_eur = st.number_input("Kwota w EUR (€)", value=0.0, step=50.0)
    cost_czk = st.number_input("Kwota w CZK (KORONY)", value=0.0, step=100.0)
    
    st.markdown("---")
    st.markdown("**Kursy walut dla kosztów:**")
    rate_costs_eur = st.number_input("Kurs EUR do kosztów -> PLN", value=4.30, step=0.01)
    rate_czk = st.number_input("Kurs CZK -> PLN", value=0.17, step=0.01)
    
    st.markdown("---")
    total_liters = st.number_input("⛽ Zatankowane litry (L)", value=0.0, step=10.0, help="Potrzebne do wyliczenia średniego spalania")

calculate_btn = st.sidebar.button("🚀 Oblicz koszty i zysk", type="primary", use_container_width=True)

if calculate_btn:
    if start_date > end_date:
        st.error("⚠️ Data początkowa nie może być późniejsza niż końcowa!")
    else:
        with st.spinner("Przetwarzanie danych..."):
            # Pobieranie dystansu z Ruptela lub opcji ręcznej
            ruptela = RuptelaAPI("https://track2.ruptela.com/api", ruptela_api_key)
            km_gps = ruptela.get_trip_distance(vehicle_plate, start_date, end_date)
            
            final_km = km_gps if km_gps > 0 else (manual_km if manual_km > 0 else 1000.0)

            # Obliczenia przychodu (Amazon w EUR na PLN)
            amazon_rate_pln = amazon_rate_eur * rate_amazon_eur

            # Obliczenia kosztów w PLN
            cost_eur_in_pln = cost_eur * rate_costs_eur
            cost_czk_in_pln = cost_czk * rate_czk
            total_uta_pln = cost_pln + cost_eur_in_pln + cost_czk_in_pln

            num_days = (end_date - start_date).days + 1
            total_fixed = num_days * daily_fixed_cost
            total_cost_pln = total_fixed + total_uta_pln
            
            # Wynik finansowy
            profit_pln = amazon_rate_pln - total_cost_pln
            profit_eur = profit_pln / rate_amazon_eur if rate_amazon_eur > 0 else 0.0
            margin = (profit_pln / amazon_rate_pln * 100) if amazon_rate_pln > 0 else 0.0
            
            cost_per_km_pln = round(total_cost_pln / final_km, 2) if final_km > 0 else 0.0
            earnings_per_km_eur = round(amazon_rate_eur / final_km, 2) if final_km > 0 else 0.0
            earnings_per_km_pln = round(amazon_rate_pln / final_km, 2) if final_km > 0 else 0.0
            avg_consumption = round((total_liters / final_km) * 100, 2) if final_km > 0 else 0.0

            # Prezentacja wyników
            st.success(f"Rozliczono pojazd **{vehicle_plate}** za okres **{start_date}** do **{end_date}** ({num_days} dni).")

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
                st.subheader("⛽ Statystyki Trasy i Paliwa")
                st.write(f"- **Dystans:** {final_km:.1f} km ({'GPS Ruptela' if km_gps > 0 else 'Wpisany ręcznie'})")
                st.write(f"- **Dni w trasie:** {num_days} dni (koszt stały {daily_fixed_cost} PLN/dzień)")
                st.write(f"- **Wpisane litry paliwa:** {total_liters} L")
                st.write(f"- **Wyliczone spalanie:** {avg_consumption} L / 100 km")
                st.write(f"- **Kurs EUR Amazon:** {rate_amazon_eur} PLN")
                st.write(f"- **Kurs EUR Koszty:** {rate_costs_eur} PLN")

            st.markdown("---")
            report_df = pd.DataFrame([{
                "Pojazd": vehicle_plate,
                "Data od": start_date,
                "Data do": end_date,
                "Dni": num_days,
                "Przebieg km": final_km,
                "Stawka Amazon EUR": amazon_rate_eur,
                "Kurs EUR Amazon": rate_amazon_eur,
                "Stawka Amazon PLN": amazon_rate_pln,
                "Wydatki PLN": cost_pln,
                "Wydatki EUR (€)": cost_eur,
                "Wydatki CZK": cost_czk,
                "Suma UTA w PLN": total_uta_pln,
                "Litry L": total_liters,
                "Spalanie L/100km": avg_consumption,
                "Koszty stale PLN": total_fixed,
                "Suma kosztow PLN": total_cost_pln,
                "Zysk czysty PLN": profit_pln,
                "Zysk czysty EUR": profit_eur,
                "Marza %": round(margin, 2),
                "Koszt PLN/km": cost_per_km_pln,
                "Stawka EUR/km": earnings_per_km_eur
            }])

            csv_export = report_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 Pobierz Wynik do Excela / CSV",
                data=csv_export,
                file_name=f"Raport_Amazon_{vehicle_plate}_{start_date}_{end_date}.csv",
                mime="text/csv",
                type="primary"
            )
else:
    st.info("👈 Wypełnij dane w lewym panelu i kliknij **'Oblicz koszty i zysk'**.")
