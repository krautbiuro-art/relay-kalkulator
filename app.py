import streamlit as st
import pandas as pd
from datetime import date, timedelta
import requests
from typing import Dict, Any, Tuple

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
    def __init__(self, api_key: str, base_host: str):
        self.base_url = f"{base_host.rstrip('/')}/v1"
        self.api_key = api_key.strip()

    def get_vehicle_data(self, vehicle_plate: str, start_date: date, end_date: date) -> Tuple[float, float, str]:
        """
        Pobiera Dystans (km) oraz Zużyte Paliwo (L) z Rupteli.
        """
        if not self.api_key:
            return 0.0, 0.0, "Brak wpisanego klucza API."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-KEY": self.api_key,
            "Accept": "application/json"
        }
        
        # Endpointy w systemie Ruptela / TrustTrack
        endpoint = f"{self.base_url}/reports/trips"
        params = {
            "plate_number": vehicle_plate.replace(" ", ""),
            "plate": vehicle_plate.replace(" ", ""),
            "from": f"{start_date}T00:00:00Z",
            "to": f"{end_date}T23:59:59Z"
        }
        
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                trips = data.get("trips", []) or data.get("items", []) or (data if isinstance(data, list) else [])
                
                if not trips:
                    return 0.0, 0.0, f"Połączono z API, ale brak tras dla rejestracji '{vehicle_plate}' w wybranym okresie."

                total_distance_m = 0.0
                total_fuel_l = 0.0

                for trip in trips:
                    total_distance_m += float(trip.get("distance", trip.get("length", 0)))
                    total_fuel_l += float(trip.get("fuel_consumed", trip.get("fuel", 0)))

                dist_km = round(total_distance_m / 1000.0, 2) if total_distance_m > 10000 else round(total_distance_m, 2)
                fuel_l = round(total_fuel_l, 2)
                
                return dist_km, fuel_l, "OK"

            elif response.status_code in (401, 403):
                return 0.0, 0.0, "Błąd autoryzacji (401/403): Nieprawidłowy Klucz API."
            else:
                return 0.0, 0.0, f"Serwer odpowiedział kodem: {response.status_code}. Treść: {response.text[:100]}"

        except requests.exceptions.Timeout:
            return 0.0, 0.0, "Przekroczono czas oczekiwania (Timeout). Sprawdź wybrany serwer API Ruptela."
        except Exception as e:
            return 0.0, 0.0, f"Błąd połączenia: {e}"

# ==========================================
# INTERFEJS GŁÓWNY
# ==========================================
st.title("🚚 Kalkulator Kosztów i Zysku Tras (Ruptela + Amazon)")
st.caption("Aplikacja do automatycznego pobierania spalania/kilometrów z Rupteli oraz rozliczania tras.")

st.sidebar.header("⚙️ Ustawienia i dane wejściowe")

# RUPTELA CONFIG
with st.sidebar.expander("🔑 Ustawienia Ruptela API", expanded=True):
    ruptela_api_key = st.text_input("Podaj Klucz API (API Key)", type="password", value="", help="Wklej klucz API Ruptela")
    server_url = st.selectbox(
        "Serwer Ruptela API", 
        ["https://track2.ruptela.com/api", "https://api.ruptela.com", "https://trusttrack.ruptela.com/api"],
        index=0,
        help="Jeśli główny serwer daje timeout, zmień na wyższy z listy."
    )

vehicle_plate = st.sidebar.text_input("🚛 Numer rejestracyjny pojazdu", value="KN0782G").strip().upper()

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("Data od", value=date.today() - timedelta(days=7))
end_date = col_d2.date_input("Data do", value=date.today())

daily_fixed_cost = st.sidebar.number_input("💵 Koszt stały auta (PLN / dzień)", value=1140.0, step=10.0)
manual_km = st.sidebar.number_input("🗺️ Przebieg km (zapasowy, jeśli brak API)", value=0.0, step=50.0)

# ==========================================
# STAWKA AMAZON W EUR
# ==========================================
with st.sidebar.expander("📦 Stawka za Blok Amazon (€)", expanded=True):
    amazon_rate_eur = st.number_input("Stawka za blok w EUR (€)", value=4942.40, step=100.0)
    rate_amazon_eur = st.number_input("Kurs EUR dla stawki (EUR -> PLN)", value=4.31, step=0.01)

# ==========================================
# FORMULARZ KOSZTÓW UTA
# ==========================================
with st.sidebar.expander("💳 Wydatki z UTA (Ręcznie)", expanded=False):
    cost_pln = st.number_input("Kwota w PLN", value=0.0, step=50.0)
    cost_eur = st.number_input("Kwota w EUR (€)", value=0.0, step=50.0)
    cost_czk = st.number_input("Kwota w CZK (KORONY)", value=0.0, step=100.0)
    
    st.markdown("---")
    rate_costs_eur = st.number_input("Kurs EUR do kosztów -> PLN", value=4.30, step=0.01)
    rate_czk = st.number_input("Kurs CZK -> PLN", value=0.17, step=0.01)
    
    st.markdown("---")
    manual_liters = st.number_input("⛽ Zatankowane litry z faktury/UTA (zapasowo)", value=0.0, step=10.0)

calculate_btn = st.sidebar.button("🚀 Pobierz dane z Rupteli i Oblicz", type="primary", use_container_width=True)

if calculate_btn:
    if start_date > end_date:
        st.error("⚠️ Data początkowa nie może być późniejsza niż końcowa!")
    else:
        with st.spinner("Łączenie z serwerem Ruptela... Pobieranie przebiegu i paliwa..."):
            ruptela = RuptelaAPI(ruptela_api_key, server_url)
            km_gps, fuel_ruptela_l, api_status = ruptela.get_vehicle_data(vehicle_plate, start_date, end_date)
            
            # Weryfikacja dystansu
            if km_gps > 0:
                final_km = km_gps
                st.success(f"✅ Pobrano z Ruptela API: **{km_gps:.1f} km**")
            else:
                final_km = manual_km if manual_km > 0 else 1000.0
                st.warning(f"⚠️ **Powiadomienie Ruptela API:** {api_status}")
                if manual_km > 0:
                    st.info(f"Użyto dystansu wpisanego ręcznie: **{manual_km:.1f} km**.")

            # Zużyte paliwo i spalanie
            used_fuel = fuel_ruptela_l if fuel_ruptela_l > 0 else manual_liters
            fuel_source = "Ruptela Telematyka" if fuel_ruptela_l > 0 else ("Wpisane ręcznie" if manual_liters > 0 else "Brak")

            # Przychód z Amazona
            amazon_rate_pln = amazon_rate_eur * rate_amazon_eur

            # Koszty
            cost_eur_in_pln = cost_eur * rate_costs_eur
            cost_czk_in_pln = cost_czk * rate_czk
            total_uta_pln = cost_pln + cost_eur_in_pln + cost_czk_in_pln

            num_days = (end_date - start_date).days + 1
            total_fixed = num_days * daily_fixed_cost
            total_cost_pln = total_fixed + total_uta_pln
            
            # Wynik
            profit_pln = amazon_rate_pln - total_cost_pln
            profit_eur = profit_pln / rate_amazon_eur if rate_amazon_eur > 0 else 0.0
            margin = (profit_pln / amazon_rate_pln * 100) if amazon_rate_pln > 0 else 0.0
            
            cost_per_km_pln = round(total_cost_pln / final_km, 2) if final_km > 0 else 0.0
            earnings_per_km_eur = round(amazon_rate_eur / final_km, 2) if final_km > 0 else 0.0
            earnings_per_km_pln = round(amazon_rate_pln / final_km, 2) if final_km > 0 else 0.0
            
            avg_consumption = round((used_fuel / final_km) * 100, 2) if final_km > 0 and used_fuel > 0 else 0.0

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
                st.subheader("⛽ Statystyki Trasy i Spalania (Ruptela)")
                st.write(f"- **Dystans:** {final_km:.1f} km ({'✅ Ruptela GPS' if km_gps > 0 else 'Wpisany ręcznie'})")
                st.write(f"- **Zużyte paliwo:** {used_fuel:.1f} L ({fuel_source})")
                st.write(f"- **Średnie spalanie:** **{avg_consumption:.2f} L / 100 km**")
                st.write(f"- **Dni w trasie:** {num_days} dni (koszt stały {daily_fixed_cost} PLN/dzień)")
                st.write(f"- **Kurs EUR Amazon:** {rate_amazon_eur} PLN")

            st.markdown("---")
            report_df = pd.DataFrame([{
                "Pojazd": vehicle_plate,
                "Data od": start_date,
                "Data do": end_date,
                "Dni": num_days,
                "Przebieg km": final_km,
                "Zuzycie paliwa L": used_fuel,
                "Spalanie L/100km": avg_consumption,
                "Stawka Amazon EUR": amazon_rate_eur,
                "Stawka Amazon PLN": amazon_rate_pln,
                "Suma kosztow PLN": total_cost_pln,
                "Zysk czysty PLN": profit_pln,
                "Zysk czysty EUR": profit_eur,
                "Marza %": round(margin, 2),
                "Koszt PLN/km": cost_per_km_pln
            }])

            csv_export = report_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 Pobierz Raport CSV / Excel",
                data=csv_export,
                file_name=f"Raport_Ruptela_{vehicle_plate}_{start_date}_{end_date}.csv",
                mime="text/csv",
                type="primary"
            )
else:
    st.info("👈 Wklej Klucz API Ruptela po lewej stronie i kliknij **'Pobierz dane z Rupteli i Oblicz'**.")
