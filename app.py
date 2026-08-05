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
    st.caption("Aplikacja do rozliczania tras (Ruptela + UTA)")
    
    password = st.text_input("Wpisz hasło dostępu:", type="password")
    
    # TUTAJ MOŻESZ ZMIENIĆ HASŁO DO APLIKACJI (domyślnie: biuro2026)
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
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None

    def authenticate(self) -> bool:
        auth_url = f"{self.base_url}/v1/auth/login"
        payload = {"username": self.username, "password": self.password}
        try:
            response = requests.post(auth_url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token") or data.get("access_token")
                return True
            return False
        except Exception:
            return False

    def get_trip_distance(self, vehicle_plate: str, start_date: date, end_date: date) -> float:
        if not self.token and not self.authenticate():
            return 0.0

        headers = {"Authorization": f"Bearer {self.token}"}
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
# 2. MODUŁ PARSERA UTA
# ==========================================
class UTAParser:
    @staticmethod
    def load_transactions(file) -> pd.DataFrame:
        if file.name.endswith('.csv'):
            try:
                df = pd.read_csv(file, sep=';', encoding='utf-8')
            except Exception:
                file.seek(0)
                df = pd.read_csv(file, sep=',', encoding='utf-8')
        elif file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            raise ValueError("Nieobsługiwany format pliku. Wgraj CSV lub XLSX.")
        
        df.columns = df.columns.str.strip()
        return df

    @staticmethod
    def calculate_vehicle_costs(df: pd.DataFrame, vehicle_plate: str, start_date: date, end_date: date) -> Dict[str, Any]:
        date_col = next((c for c in df.columns if 'data' in c.lower() or 'date' in c.lower()), None)
        plate_col = next((c for c in df.columns if 'rejestracyjny' in c.lower() or 'plate' in c.lower() or 'pojazd' in c.lower() or 'karta' in c.lower()), None)
        cat_col = next((c for c in df.columns if 'kategoria' in c.lower() or 'produkt' in c.lower() or 'opis' in c.lower() or 'artykuł' in c.lower()), None)
        amount_col = next((c for c in df.columns if 'netto' in c.lower() or 'kwota' in c.lower() or 'wartosc' in c.lower()), None)
        qty_col = next((c for c in df.columns if 'ilość' in c.lower() or 'ilosc' in c.lower() or 'litry' in c.lower()), None)

        if not all([date_col, plate_col, cat_col, amount_col]):
            st.warning("Uwaga: Plik z UTA został wczytany, ale niektóre nazwy kolumn różnią się od standardowych.")

        df['Data_dt'] = pd.to_datetime(df[date_col], errors='coerce') if date_col else pd.NaT
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        clean_plate = vehicle_plate.replace(" ", "").upper()
        
        filtered = df
        if plate_col:
            filtered = filtered[filtered[plate_col].astype(str).str.replace(" ", "").str.upper().str.contains(clean_plate, na=False)]
        if date_col:
            filtered = filtered[(filtered['Data_dt'] >= start_dt) & (filtered['Data_dt'] <= end_dt)]

        if filtered.empty:
            return {"paliwo_netto": 0.0, "oplaty_drogowe_netto": 0.0, "litry_paliwa": 0.0, "tabela_transakcji": pd.DataFrame()}

        paliwo_mask = filtered[cat_col].astype(str).str.contains('Paliwo|Diesel|ON|Fuel', case=False, na=False) if cat_col else pd.Series(True, index=filtered.index)
        oplaty_mask = filtered[cat_col].astype(str).str.contains('Opłata|Toll|e-TOLL|Tunel|Autostrada|Road', case=False, na=False) if cat_col else pd.Series(False, index=filtered.index)

        paliwo_netto = pd.to_numeric(filtered.loc[paliwo_mask, amount_col].astype(str).str.replace(',', '.'), errors='coerce').sum() if amount_col else 0.0
        oplaty_netto = pd.to_numeric(filtered.loc[oplaty_mask, amount_col].astype(str).str.replace(',', '.'), errors='coerce').sum() if amount_col else 0.0
        
        litry = 0.0
        if qty_col:
            litry = pd.to_numeric(filtered.loc[paliwo_mask, qty_col].astype(str).str.replace(',', '.'), errors='coerce').sum()

        return {
            "paliwo_netto": round(float(paliwo_netto), 2),
            "oplaty_drogowe_netto": round(float(oplaty_netto), 2),
            "litry_paliwa": round(float(litry), 2),
            "tabela_transakcji": filtered
        }

# ==========================================
# INTERFEJS GŁÓWNY
# ==========================================
st.title("🚚 Kalkulator Kosztów Tras (Ruptela + UTA)")
st.caption("Aplikacja dla biura do automatycznego przeliczania trasy, paliwa i opłat drogowych.")

st.sidebar.header("⚙️ Ustawienia i dane wejściowe")

with st.sidebar.expander("🔑 Logowanie Ruptela API"):
    ruptela_user = st.text_input("Użytkownik Ruptela", value="")
    ruptela_pass = st.text_input("Hasło Ruptela", type="password", value="")

vehicle_plate = st.sidebar.text_input("🚛 Numer rejestracyjny pojazdu", value="WI12345").strip().upper()

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("Data od", value=date.today() - timedelta(days=7))
end_date = col_d2.date_input("Data do", value=date.today())

daily_fixed_cost = st.sidebar.number_input("💵 Koszt stały auta (PLN / dzień)", value=180.0, step=10.0)
manual_km = st.sidebar.number_input("🗺️ Przebieg km (jeśli brak połączenia API)", value=0.0, step=50.0)

uploaded_file = st.sidebar.file_uploader("📂 Wgraj plik z fakturą UTA (CSV / XLSX)", type=["csv", "xlsx", "xls"])

calculate_btn = st.sidebar.button("🚀 Oblicz koszty trasy", type="primary", use_container_width=True)

if calculate_btn:
    if not uploaded_file:
        st.error("⚠️ Proszę wgrać plik z fakturą UTA w panelu po lewej stronie!")
    elif start_date > end_date:
        st.error("⚠️ Data początkowa nie może być późniejsza niż końcowa!")
    else:
        with st.spinner("Przetwarzanie danych..."):
            ruptela = RuptelaAPI("https://track2.ruptela.com/api", ruptela_user, ruptela_pass)
            km_gps = ruptela.get_trip_distance(vehicle_plate, start_date, end_date)
            
            final_km = km_gps if km_gps > 0 else (manual_km if manual_km > 0 else 1000.0)

            try:
                df_uta = UTAParser.load_transactions(uploaded_file)
                uta_res = UTAParser.calculate_vehicle_costs(df_uta, vehicle_plate, start_date, end_date)
            except Exception as e:
                st.error(f"Błąd podczas odczytu pliku UTA: {e}")
                st.stop()

            num_days = (end_date - start_date).days + 1
            total_fixed = num_days * daily_fixed_cost
            total_variable = uta_res["paliwo_netto"] + uta_res["oplaty_drogowe_netto"]
            total_cost = total_fixed + total_variable
            
            cost_per_km = round(total_cost / final_km, 2) if final_km > 0 else 0.0
            avg_consumption = round((uta_res["litry_paliwa"] / final_km) * 100, 2) if final_km > 0 else 0.0

            st.success(f"Rozliczono pojazd **{vehicle_plate}** za okres **{start_date}** do **{end_date}** ({num_days} dni).")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Łączny Przebieg", f"{final_km:.1f} km", delta="GPS Ruptela" if km_gps > 0 else "Ręczny / Wzorcowy")
            m2.metric("Suma Kosztów", f"{total_cost:.2f} PLN")
            m3.metric("Koszt 1 km", f"{cost_per_km:.2f} PLN/km")
            m4.metric("Średnie Spalanie", f"{avg_consumption:.2f} L/100km")

            st.markdown("---")

            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("📊 Podsumowanie Kosztów")
                summary_data = {
                    "Kategoria": ["Paliwo (netto)", "Opłaty drogowe (netto)", "Koszty stałe (leasing/ubezpieczenie)", "SUMA CAŁKOWITA"],
                    "Kwota (PLN)": [uta_res["paliwo_netto"], uta_res["oplaty_drogowe_netto"], total_fixed, round(total_cost, 2)],
                }
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

            with col_right:
                st.subheader("⛽ Dane Paliwowe")
                st.write(f"- **Ilość paliwa:** {uta_res['litry_paliwa']} L")
                st.write(f"- **Średnie spalanie:** {avg_consumption} L / 100 km")
                st.write(f"- **Dni w trasie:** {num_days} dni (stawką {daily_fixed_cost} PLN/dzień)")

            if not uta_res["tabela_transakcji"].empty:
                st.markdown("---")
                st.subheader("🧾 Transakcje przypisane do tego auta z pliku UTA")
                st.dataframe(uta_res["tabela_transakcji"], use_container_width=True)

            st.markdown("---")
            report_df = pd.DataFrame([{
                "Pojazd": vehicle_plate,
                "Data od": start_date,
                "Data do": end_date,
                "Dni": num_days,
                "Przebieg km": final_km,
                "Paliwo PLN": uta_res["paliwo_netto"],
                "Litry L": uta_res["litry_paliwa"],
                "Spalanie L/100km": avg_consumption,
                "Oplaty drogowe PLN": uta_res["oplaty_drogowe_netto"],
                "Koszty stale PLN": total_fixed,
                "Suma kosztow PLN": total_cost,
                "Koszt PLN/km": cost_per_km
            }])

            csv_export = report_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 Pobierz Wynik do Excela / CSV",
                data=csv_export,
                file_name=f"Raport_{vehicle_plate}_{start_date}_{end_date}.csv",
                mime="text/csv",
                type="primary"
            )
else:
    st.info("👈 Wypełnij dane w lewym panelu i kliknij **'Oblicz koszty trasy'**.")
