import streamlit as st
import pandas as pd
from datetime import date, timedelta
import requests

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
    st.caption("Aplikacja do rozliczania tras (Ruptela + Amazon)")
    
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
# MODUŁ AUTOBIERANIA DANYCH Z RUPTELI
# ==========================================
def fetch_ruptela_data(username, password, plate, start_date, end_date):
    """Pobiera przebieg i paliwo bezpośrednio z track2.ruptela.com"""
    if not username or not password:
        return 0.0, 0.0, "Brak wpisanych danych logowania Ruptela"

    clean_plate = plate.replace(" ", "").upper()
    session = requests.Session()
    
    # 1. Logowanie i pobranie tokenu
    login_url = "https://track2.ruptela.com/api/v1/auth/login"
    payload = {"username": username, "password": password}
    
    try:
        res = session.post(login_url, json=payload, timeout=8)
        if res.status_code != 200:
            return 0.0, 0.0, f"Błąd logowania Ruptela (Kod: {res.status_code})"
        
        token = res.json().get("token") or res.json().get("access_token")
        if not token:
            return 0.0, 0.0, "Nie otrzymano tokenu autoryzacji"

        # 2. Pobieranie raportu tras
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        report_url = "https://track2.ruptela.com/api/v1/reports/trips"
        params = {
            "plate": clean_plate,
            "from": f"{start_date}T00:00:00Z",
            "to": f"{end_date}T23:59:59Z"
        }
        
        rep_res = session.get(report_url, headers=headers, params=params, timeout=10)
        if rep_res.status_code == 200:
            data = rep_res.json()
            trips = data.get("trips") or data.get("items") or (data if isinstance(data, list) else [])
            
            if trips:
                total_dist = sum([float(t.get("distance", t.get("length", 0))) for t in trips if isinstance(t, dict)])
                total_fuel = sum([float(t.get("fuel_consumed", t.get("fuel", 0))) for t in trips if isinstance(t, dict)])
                
                dist_km = round(total_dist / 1000.0, 2) if total_dist > 10000 else round(total_dist, 2)
                return dist_km, round(total_fuel, 2), "OK"
            else:
                return 0.0, 0.0, f"Brak zarejestrowanych tras w podanym okresie dla {clean_plate}"
        else:
            return 0.0, 0.0, f"Błąd raportu z Rupteli ({rep_res.status_code})"
            
    except Exception as e:
        return 0.0, 0.0, f"Błąd połączenia: {str(e)}"

# ==========================================
# INTERFEJS GŁÓWNY
# ==========================================
st.title("🚚 Kalkulator Kosztów i Zysku Tras")
st.caption("Automatyczne rozliczanie tras (Pobieranie danych z Rupteli + Koszty UTA + Stawka Amazon)")

st.sidebar.header("⚙️ Ustawienia i dane trasy")

# RUPTELA CREDENTIALS
with st.sidebar.expander("🔑 Logowanie Track2 Ruptela (API)", expanded=True):
    rup_user = st.text_input("Login Ruptela", value="KrautRup99", help="Login do track2.ruptela.com")
    rup_pass = st.text_input("Hasło Ruptela", type="password", value="", help="Hasło do track2.ruptela.com")
    use_ruptela = st.checkbox("Zaciągaj dane z Ruptela GPS", value=True)

vehicle_plate = st.sidebar.text_input("🚛 Numer rejestracyjny pojazdu", value="KN0782G").strip().upper()

col_d1, col_d2 = st.sidebar.columns(2)
start_date = col_d1.date_input("Data od", value=date.today() - timedelta(days=7))
end_date = col_d2.date_input("Data do", value=date.today())

daily_fixed_cost = st.sidebar.number_input("💵 Koszt stały auta (PLN / dzień)", value=1140.0, step=10.0)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Dystans i Paliwo (Wpisz ręcznie jeśli brak GPS)")
manual_km = st.sidebar.number_input("🗺️ Przebieg km", value=4415.8, step=10.0)
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
with st.sidebar.expander("💳 Wydatki z UTA / Drogowe", expanded=False):
    cost_pln = st.number_input("Kwota w PLN", value=0.0, step=50.0)
    cost_eur = st.number_input("Kwota w EUR (€)", value=0.0, step=50.0)
    cost_czk = st.number_input("Kwota w CZK (KORONY)", value=0.0, step=100.0)
    
    st.markdown("---")
    rate_costs_eur = st.number_input("Kurs EUR do kosztów -> PLN", value=4.30, step=0.01)
    rate_czk = st.number_input("Kurs CZK -> PLN", value=0.17, step=0.01)

calculate_btn = st.sidebar.button("🚀 Zaciągnij dane i Przelicz", type="primary", use_container_width=True)

if calculate_btn:
    if start_date > end_date:
        st.error("⚠️ Data początkowa nie może być późniejsza niż końcowa!")
    else:
        gps_km, gps_fuel, status_msg = 0.0, 0.0, "Tryb ręczny"
        
        # Próba zaciągnięcia danych z Ruptela API
        if use_ruptela:
            with st.spinner("Łączenie z track2.ruptela.com i pobieranie danych GPS..."):
                gps_km, gps_fuel, status_msg = fetch_ruptela_data(rup_user, rup_pass, vehicle_plate, start_date, end_date)

        # Ustalenie ostatecznych wartości kilometrów i paliwa
        if gps_km > 0:
            final_km = gps_km
            used_fuel = gps_fuel
            data_source = "✅ Pobrano automatycznie z Ruptela GPS"
            st.success(f"{data_source}: **{final_km:.1f} km** | Paliwo: **{used_fuel:.1f} L**")
        else:
            final_km = manual_km if manual_km > 0 else 1000.0
            used_fuel = manual_liters
            data_source = f"ℹ️ Dane wpisane ręcznie ({status_msg})"
            st.info(f"{data_source} | Dystans: **{final_km:.1f} km**")

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
            st.subheader("⛽ Statystyki Trasy i Źródło")
            st.write(f"- **Pojazd:** {vehicle_plate}")
            st.write(f"- **Źródło przebiegu:** {data_source}")
            st.write(f"- **Dystans trasy:** {final_km:.1f} km")
            st.write(f"- **Dni w trasie:** {num_days} dni (koszt stały {daily_fixed_cost} PLN/dzień)")
            if used_fuel > 0:
                st.write(f"- **Zużyte paliwo:** {used_fuel:.1f} L")
                if avg_consumption > 0:
                    st.write(f"- **Średnie spalanie:** {avg_consumption:.2f} L / 100 km")
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
    st.info("👈 Uzupełnij hasło Ruptela i kliknij **'Zaciągnij dane i Przelicz'**.")
