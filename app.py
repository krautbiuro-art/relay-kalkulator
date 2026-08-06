import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Koszty Floty",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🚛 Rozliczenie Floty - Ruptela API")

API_KEY = st.secrets.get("RUPTELA_API_KEY", "")

if not API_KEY:
    st.error("❌ Brak klucza RUPTELA_API_KEY w Secrets!")
    st.stop()

@st.cache_data(ttl=120)
def fetch_ruptela_fleet(api_key):
    # 1. Pobieranie listy pojazdów
    url_vehicles = f"https://api.fm-track.com/objects?version=1&api_key={api_key}"
    resp = requests.get(url_vehicles, timeout=10)
    
    if resp.status_code != 200:
        st.error(f"Błąd podczas pobierania pojazdów: {resp.status_code}")
        return []
        
    vehicles_data = resp.json()
    fleet_list = []

    # 2. Iteracja po pojazdach i pobieranie ich najnowszej telemetrii
    for v in vehicles_data:
        v_id = v.get("id")
        v_name = v.get("name", "Brak nazwy")
        v_params = v.get("vehicle_params", {})
        make = v_params.get("make", "")
        model = v_params.get("model", "")
        full_name = f"{v_name} ({make} {model})".strip()
        
        # Zapytanie o ostatnie odczyty (last-points / telemetry)
        url_telemetry = f"https://api.fm-track.com/objects/{v_id}/last-point?version=1&api_key={api_key}"
        tel_resp = requests.get(url_telemetry, timeout=10)
        
        mileage_km = 0.0
        fuel_consumed_l = 0.0
        
        if tel_resp.status_code == 200:
            tel_data = tel_resp.json()
            # Wyciągamy dane z payloadu telemetrycznego (dostosowujemy w zależności od zwróconych kluczy)
            payload = tel_data.get("payload", {})
            mileage_km = payload.get("mileage", 0.0)
            fuel_consumed_l = payload.get("total_fuel_used", 0.0)

        fleet_list.append({
            "Pojazd_ID": v_id,
            "Pojazd": full_name,
            "Dystans_km": float(mileage_km),
            "Spalanie_L": float(fuel_consumed_l)
        })

    return fleet_list

data = fetch_ruptela_fleet(API_KEY)

if data:
    df = pd.DataFrame(data)

    # SECJA INPUTÓW KOSZTOWYCH
    st.subheader("⚙️ Parametry kosztowe")
    col1, col2 = st.columns(2)
    with col1:
        cena_paliwa = st.number_input("Cena ON za litr (PLN netto):", value=6.20, step=0.05, format="%.2f")
    with col2:
        oplaty_drogowe = st.number_input("Dodatkowe koszty / e-TOLL (PLN):", value=0.0, step=50.0)

    # KALKULACJA
    df["Koszt_Paliwa"] = df["Spalanie_L"] * cena_paliwa
    
    # Wyliczanie średniego spalania na 100km (jeśli dystans > 0)
    df["Średnie_l/100km"] = df.apply(
        lambda r: (r["Spalanie_L"] / r["Dystans_km"] * 100) if r["Dystans_km"] > 0 else 0, axis=1
    )

    suma_km = df["Dystans_km"].sum()
    suma_litry = df["Spalanie_L"].sum()
    suma_koszt_paliwa = df["Koszt_Paliwa"].sum()
    calkowity_koszt = suma_koszt_paliwa + oplaty_drogowe
    sredni_koszt_km = calkowity_koszt / suma_km if suma_km > 0 else 0.0

    # WSKAŹNIKI KOSZTOWE (KPI)
    st.divider()
    st.subheader("📊 Podsumowanie floty")
    
    k1, k2 = st.columns(2)
    k3, k4 = st.columns(2)
    
    k1.metric("Łączny Dystans", f"{suma_km:,.1f} km".replace(",", " "))
    k2.metric("Zużyte Paliwo", f"{suma_litry:,.1f} L".replace(",", " "))
    k3.metric("Łączny Koszt", f"{calkowity_koszt:,.2f} PLN".replace(",", " "))
    k4.metric("Koszt na 1 km", f"{sredni_koszt_km:.2f} PLN/km")

    # TABELA POJAZDÓW
    st.divider()
    st.subheader("📋 Tabela kosztowa wg pojazdów")
    st.dataframe(
        df[["Pojazd", "Dystans_km", "Spalanie_L", "Średnie_l/100km", "Koszt_Paliwa"]],
        use_container_width=True
    )
