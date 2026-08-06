import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Koszty Floty - Ruptela",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚛 Rozliczenie Kosztów Floty - Ruptela API")

API_KEY = st.secrets.get("RUPTELA_API_KEY", "")

if not API_KEY:
    st.error("❌ Brak klucza RUPTELA_API_KEY w Secrets!")
    st.stop()

# --- 1. POBIERANIE LISTY POJAZDÓW ---
@st.cache_data(ttl=300)
def get_vehicles_list(api_key):
    url = f"https://api.fm-track.com/objects?version=1&api_key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []

# --- 2. POBIERANIE HISTORII / TELEMETRII W DANYM ZAKRESIE DAT ---
@st.cache_data(ttl=60)
def get_vehicle_history(api_key, vehicle_id, date_from, date_to):
    # Endpoint do pobierania punktów/raportu z danego okresu
    # Formatuje daty do ISO UTC
    from_str = date_from.strftime("%Y-%m-%dT00:00:00Z")
    to_str = date_to.strftime("%Y-%m-%dT23:59:59Z")
    
    url = f"https://api.fm-track.com/objects/{vehicle_id}/points?version=1&from={from_str}&to={to_str}&api_key={api_key}"
    
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            points = resp.json()
            if not points or not isinstance(points, list):
                return 0.0, 0.0
            
            # Liczymy różnicę przebiegu i zużycia paliwa z pierwszego i ostatniego punktu trasy
            first_point = points[0].get("payload", {})
            last_point = points[-1].get("payload", {})
            
            start_km = first_point.get("mileage", 0.0)
            end_km = last_point.get("mileage", 0.0)
            
            start_fuel = first_point.get("total_fuel_used", 0.0)
            end_fuel = last_point.get("total_fuel_used", 0.0)
            
            dystans = max(0.0, float(end_km - start_km))
            spalanie = max(0.0, float(end_fuel - start_fuel))
            
            return dystans, spalanie
        return 0.0, 0.0
    except Exception:
        return 0.0, 0.0

# --- SEKCJA FILTRÓW ---
st.sidebar.header("🔍 Filtry i Ustawienia")

vehicles = get_vehicles_list(API_KEY)
options_map = {"Wszystkie pojazdy": "ALL"}

for v in vehicles:
    v_id = v.get("id")
    name = v.get("name", "Brak nazwy")
    options_map[name] = v_id

wybrane_auto_label = st.sidebar.selectbox("Wybierz pojazd:", list(options_map.keys()))
wybrany_id = options_map[wybrane_auto_label]

# Domyślnie zakres z ostatnich 7 dni
dzis = datetime.now()
siedem_dni_temu = dzis - timedelta(days=7)

data_od = st.sidebar.date_input("Data od:", siedem_dni_temu)
data_do = st.sidebar.date_input("Data do:", dzis)

st.sidebar.divider()
st.sidebar.header("⚙️ Parametry kosztowe")
cena_paliwa = st.sidebar.number_input("Cena ON za litr (PLN netto):", value=6.20, step=0.05, format="%.2f")
oplaty_drogowe = st.sidebar.number_input("Dodatkowe koszty / e-TOLL (PLN):", value=0.0, step=50.0)

# --- PRZETWARZANIE DANYCH ---
flota_dane = []

with st.spinner("Pobieranie i przeliczanie danych z Rupteli..."):
    if wybrany_id == "ALL":
        # Dla wszystkich aut
        for v in vehicles:
            v_id = v.get("id")
            v_name = v.get("name", "Pojazd")
            dystans, spalanie = get_vehicle_history(API_KEY, v_id, data_od, data_do)
            flota_dane.append({
                "Pojazd": v_name,
                "Dystans_km": dystans,
                "Spalanie_L": spalanie
            })
    else:
        # Dla wybranego konkretnego auta
        dystans, spalanie = get_vehicle_history(API_KEY, wybrany_id, data_od, data_do)
        flota_dane.append({
            "Pojazd": wybrane_auto_label,
            "Dystans_km": dystans,
            "Spalanie_L": spalanie
        })

df = pd.DataFrame(flota_dane)

# KONTROLA BRAKU DANYCH
if df.empty or df["Dystans_km"].sum() == 0:
    st.info(f"ℹ️ Brak zarejestrowanych tras/punktów GPS dla wybranego zakresu dat ({data_od} - {data_do}). Wybierz inny zakres.")
else:
    # KALKULACJE KOSZTOWE
    df["Koszt_Paliwa"] = df["Spalanie_L"] * cena_paliwa
    df["Średnie_l/100km"] = df.apply(
        lambda r: (r["Spalanie_L"] / r["Dystans_km"] * 100) if r["Dystans_km"] > 0 else 0, axis=1
    )

    suma_km = df["Dystans_km"].sum()
    suma_litry = df["Spalanie_L"].sum()
    suma_koszt_paliwa = df["Koszt_Paliwa"].sum()
    calkowity_koszt = suma_koszt_paliwa + oplaty_drogowe
    sredni_koszt_km = calkowity_koszt / suma_km if suma_km > 0 else 0.0

    # WSKAŹNIKI (KPI)
    st.subheader(f"📊 Wyniki dla okresu: {data_od.strftime('%d.%m.%Y')} - {data_do.strftime('%d.%m.%Y')}")
    
    k1, k2 = st.columns(2)
    k3, k4 = st.columns(2)
    
    k1.metric("Łączny Dystans", f"{suma_km:,.1f} km".replace(",", " "))
    k2.metric("Zużyte Paliwo", f"{suma_litry:,.1f} L".replace(",", " "))
    k3.metric("Łączny Koszt", f"{calkowity_koszt:,.2f} PLN".replace(",", " "))
    k4.metric("Koszt na 1 km", f"{sredni_koszt_km:.2f} PLN/km")

    # TABELA DANYCH
    st.divider()
    st.subheader("📋 Tabela podsumowująca")
    st.dataframe(
        df[["Pojazd", "Dystans_km", "Spalanie_L", "Średnie_l/100km", "Koszt_Paliwa"]].style.format({
            "Dystans_km": "{:.1f} km",
            "Spalanie_L": "{:.1f} L",
            "Średnie_l/100km": "{:.2f} l/100km",
            "Koszt_Paliwa": "{:.2f} PLN"
        }),
        use_container_width=True
    )
