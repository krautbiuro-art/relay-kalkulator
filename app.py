import streamlit as st
import pandas as pd
from datetime import date, timedelta
import requests
from typing import Tuple

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
# MODUŁ TRUSTTRACK / RUPTELA API (LOGIN + TOKEN)
# ==========================================
class TrustTrackAPI:
    def __init__(self, username: str, password: str, server_url: str):
        self.base_url = server_url.rstrip('/')
        self.username = username.strip()
        self.password = password.strip()
        self.session_token = None

    def authenticate(self) -> bool:
        """ Pobiera token sesyjny z TrustTrack """
        if not self.username or not self.password:
            return False
            
        auth_url = f"{self.base_url}/auth/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        try:
            res = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200 and "application/json" in res.headers.get("Content-Type", ""):
                data = res.json()
                self.session_token = data.get("token") or data.get("access_token") or data.get("key")
                return True
        except Exception:
            pass
        return False

    def get_trip_data(self, vehicle_plate: str, start_date: date, end_date: date) -> Tuple[float, float, str]:
        # Domyślnie próbujemy zalogować się danymi
        if not self.session_token:
            if not self.authenticate():
                # Jeśli logowanie loginem nie wyszło, próba podpięcia pod klucz API
                self.session_token = self.password

        clean_plate = vehicle_plate.replace(" ", "").upper()
        
        headers = {
            "Authorization": f"Bearer {self.session_token}",
            "X-API-KEY": self.session_token,
            "Accept": "application/json"
        }
        
        # Oficjalny endpoint raportów TrustTrack
        report_url = f"{self.base_url}/reports/trips"
        params = {
            "plate": clean_plate,
            "from": f"{start_date}T00:00:00Z",
            "to": f"{end_date}T23:59:59Z"
        }

        try:
            res = requests.get(report_url, headers=headers, params=params, timeout=10)
            
            if res.status_code == 200 and "application/json" in res.headers.get("Content-Type", ""):
                data = res.json()
                trips = data.get("trips") or data.get("items") or (data if isinstance(data, list) else [])
                
                if trips:
                    total_dist_m = sum([float(t.get("distance", t.get("length", 0))) for t in trips if isinstance(t, dict)])
                    total_fuel_l = sum([float(t.get("fuel_consumed", t.get("fuel", 0))) for t in trips if isinstance(t, dict)])
                    
                    dist_km = round(total_dist_m / 1000.0, 2) if total_dist_m > 10000 else round(total_dist_m, 2)
                    fuel_l = round(total_fuel_l, 2)
                    
                    if dist_km > 0:
                        return dist_km, fuel_l, "OK"
                else:
                    return 0.0, 0.0, f"Brak zarejestrowanych tras w panelu TrustTrack dla rejestracji {clean_plate}."
            elif res.status_code in (401, 403):
                return 0.0, 0.0, "Nieprawidłowy login, hasło lub klucz API TrustTrack."
        except Exception as e:
            return 0.0, 0.0, f"Błąd połączenia: {e}"

        return 0.0, 0.0, "Brak połączenia z API. Zastosowano przeliczenie ręczne."

# ==========================================
# INTERFEJS GŁÓWNY
# ==========================================
st.title("🚚 Kalkulator Kosztów i Zysku Tras (Ruptela + Amazon)")
st.caption("Aplikacja do automatycznego pobierania spalania/kilometrów z Rupteli oraz rozliczania tras.")

st.sidebar.header("⚙️ Ustawienia i dane wejściowe")

# TRUSTTRACK CONFIG
with st.sidebar.expander("🔑 Logowanie do TrustTrack / Ruptela", expanded=True):
    tt_user = st.text_input("Login / Użytkownik TrustTrack", value="", help="Login do panelu TrustTrack")
    tt_pass = st.text_input("Hasło lub Klucz API", type="password", value="", help="Hasło do konta lub Klucz API")
    
    server_url = st.selectbox(
        "Serwer TrustTrack", 
        [
            "https://trusttrack.ruptela.com/api/v1",
            "https://track2.ruptela.com/api/v1",
            "https://api.ruptela.com/v1"
        ],
        index=0
    )

vehicle_plate = st.sidebar.text_input("🚛 Numer rejestracyjny pojazdu", value="KN0782G").strip().upper()

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("Data od", value=date.today() - timedelta(days=7))
end_date = col_d2.date_input("Data do", value=date.today())

daily_fixed_cost = st.sidebar.number_input("💵 Koszt stały auta (PLN / dzień)", value=1140.0, step=10.0)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Dystans ręczny (zapasowy)")
manual_km = st.sidebar.number_input("🗺️ Przebieg km", value=4415.8, step=50.0)
manual_liters = st.sidebar.number_input("⛽ Zużyte paliwo (Litry)", value=0.0, step=10.0)

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

calculate_btn = st.sidebar.button("🚀 Przelicz koszty i zysk", type="primary", use_container_width=True)

if calculate_btn:
    if start_date > end_date:
        st.error("⚠️ Data początkowa nie może być późniejsza niż końcowa!")
    else:
        with st.spinner("Pobieranie danych i przeliczanie tras..."):
            tt_api = TrustTrackAPI(tt_user, tt_pass, server_url)
            km_gps, fuel_ruptela_l, api_status = tt_api.get_trip_data(vehicle_plate, start_date, end_date)
            
            if km_gps > 0:
                final_km = km_gps
                st.success(f"✅ Pobrano automatycznie z TrustTrack GPS: **{km_gps:.1f} km** | Paliwo: **{fuel_ruptela_l:.1f} L**")
            else:
                final_km = manual_km if manual_km > 0 else 1000.0
                st.warning(f"ℹ️ **Informacja:** {api_status}")
                st.info(f"Użyto wartości wpisanej ręcznie: **{final_km:.1f} km**")

            used_fuel = fuel_ruptela_l if fuel_ruptela_l > 0 else manual_liters
            fuel_source = "TrustTrack GPS" if fuel_ruptela_l > 0 else ("Ręcznie" if manual_liters > 0 else "Brak")

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
                st.subheader("⛽ Statystyki Trasy i Paliwa")
                st.write(f"- **Dystans:** {final_km:.1f} km ({'Wpisany ręcznie / domyślny' if km_gps == 0 else 'TrustTrack GPS'})")
                st.write(f"- **Dni w trasie:** {num_days} dni (koszt stały {daily_fixed_cost} PLN/dzień)")
                st.write(f"- **Wpisane litry paliwa:** {used_fuel:.1f} L")
                if avg_consumption > 0:
                    st.write(f"- **Wyliczone spalanie:** {avg_consumption:.2f} L / 100 km")
                st.write(f"- **Kurs EUR Amazon:** {rate_amazon_eur} PLN")

            st.markdown("---")
            report_df = pd.DataFrame([{
                "Pojazd": vehicle_plate,
                "Data od": start_date,
                "Data do": end_date,
                "Dni": num_days,
                "Przebieg km": final_km,
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
                file_name=f"Raport_Trasy_{vehicle_plate}_{start_date}_{end_date}.csv",
                mime="text/csv",
                type="primary"
            )
else:
    st.info("👈 Uzupełnij dane po lewej stronie i kliknij **'Przelicz koszty i zysk'**.")
