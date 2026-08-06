import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, time
import time as ttime

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
def get_vehicles_list(api_key):
    url = f"https://api.fm-track.com/objects?version=1&api_key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []

# --- 2. POBIERANIE TRAS I PALIWA Z PEŁNĄ DIAGNOSTYKĄ ---
def get_vehicle_stats(api_key, vehicle_id, dt_from, dt_to):
    # Czas w UTC dla API
    tz_offset = timedelta(hours=2)
    dt_from_utc = dt_from - tz_offset
    dt_to_utc = dt_to - tz_offset
    
    from_str = dt_from_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_str = dt_to_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = f"https://api.fm-track.com/objects/{vehicle_id}/trips?version=1&from_datetime={from_str}&to_datetime={to_str}&api_key={api_key}"
    
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            trips = data.get("trips", []) if isinstance(data, dict) else data
            
            if not trips:
                return 0.0, 0.0, data
            
            # Pobieramy dystans z odometru (start vs end całego okresu)
            first_trip = trips[0]
            last_trip = trips[-1]
            
            # Odczyt drogomierza
            o_start = float(first_trip.get("start_odometer") or first_trip.get("odometer") or 0)
            o_end = float(last_trip.get("end_odometer") or last_trip.get("odometer") or 0)
            
            if o_end > o_start and o_start > 0:
                dist_km = (o_end - o_start) / 1000.0
            else:
                dist_km = sum(float(t.get("mileage", 0) or 0) for t in trips) / 1000.0
                
            # Odczyt paliwa z magistrali CAN ze wszystkich pól
            fuel_l = 0.0
            for t in trips:
                f_val = t.get("fuel_consumed") or t.get("fuel_used") or t.get("fuel") or 0.0
                fuel_l += float(f_val)
                
            return dist_km, fuel_l, data
            
        return 0.0, 0.0, {"error": f"HTTP {resp.status_code}", "body": resp.text}
    except Exception as e:
        return 0.0, 0.0, {"error": str(e)}

# --- PANEL BOCZNY: FILTRY ---
st.sidebar.header("🔍 Filtry i Ustawienia")

vehicles = get_vehicles_list(API_KEY)
options_map = {"Wszystkie pojazdy": "ALL"}

for v in vehicles:
    v_id = v.get("id")
    name = v.get("name", "Brak nazwy")
    options_map[name] = v_id

wybrane_auto_label = st.sidebar.selectbox("Wybierz pojazd:", list(options_map.keys()))
wybrany_id = options_map[wybrane_auto_label]

dzis = datetime.now()
siedem_dni_temu = dzis - timedelta(days=7)

col_d1, col_t1 = st.sidebar.columns(2)
with col_d1:
    data_od = st.date_input("Data od:", siedem_dni_temu)
with col_t1:
    godz_od = st.time_input("Godzina od:", time(0, 0))

col_d2, col_t2 = st.sidebar.columns(2)
with col_d2:
    data_do = st.date_input("Data do:", dzis)
with col_t2:
    godz_do = st.time_input("Godzina do:", time(23, 59))

dt_od = datetime.combine(data_od, godz_od)
dt_do = datetime.combine(data_do, godz_do)

st.sidebar.divider()
st.sidebar.header("⚙️ Parametry kosztowe")
cena_paliwa = st.sidebar.number_input("Cena ON za litr (PLN netto):", value=6.20, step=0.05, format="%.2f")
srednia_norma = st.sidebar.number_input("Domyślna norma spalania (L/100km):", value=21.33, step=0.5)

# --- PRZETWARZANIE ---
flota_dane = []
raw_debug = {}

with st.spinner("Pobieranie danych z Ruptela API..."):
    if wybrany_id == "ALL":
        for v in vehicles:
            v_id = v.get("id")
            v_name = v.get("name", "Pojazd")
            dystans, spalanie, debug_json = get_vehicle_stats(API_KEY, v_id, dt_od, dt_do)
            
            if spalanie == 0.0 and dystans > 0:
                spalanie = (dystans / 100.0) * srednia_norma
                
            flota_dane.append({"Pojazd": v_name, "Dystans_km": dystans, "Spalanie_L": spalanie})
            raw_debug[v_name] = debug_json
    else:
        dystans, spalanie, debug_json = get_vehicle_stats(API_KEY, wybrany_id, dt_od, dt_do)
        
        if spalanie == 0.0 and dystans > 0:
            spalanie = (dystans / 100.0) * srednia_norma
            
        flota_dane.append({"Pojazd": wybrane_auto_label, "Dystans_km": dystans, "Spalanie_L": spalanie})
        raw_debug[wybrane_auto_label] = debug_json

df = pd.DataFrame(flota_dane)

if not df.empty and df["Dystans_km"].sum() > 0:
    df["Koszt_Paliwa"] = df["Spalanie_L"] * cena_paliwa
    df["Średnie_l/100km"] = df.apply(lambda r: (r["Spalanie_L"] / r["Dystans_km"] * 100) if r["Dystans_km"] > 0 else 0, axis=1)

    st.subheader(f"📊 Wyniki za okres: {dt_od.strftime('%d.%m.%Y %H:%M')} - {dt_do.strftime('%d.%m.%Y %H:%M')}")
    
    k1, k2 = st.columns(2)
    k3, k4 = st.columns(2)
    
    k1.metric("Łączny Dystans", f"{df['Dystans_km'].sum():,.2f} km".replace(",", " "))
    k2.metric("Zużyte Paliwo", f"{df['Spalanie_L'].sum():,.2f} L".replace(",", " "))
    k3.metric("Łączny Koszt", f"{df['Koszt_Paliwa'].sum():,.2f} PLN".replace(",", " "))
    k4.metric("Koszt na 1 km", f"{(df['Koszt_Paliwa'].sum() / df['Dystans_km'].sum()):.2f} PLN/km" if df['Dystans_km'].sum() > 0 else "0.00 PLN/km")

    st.dataframe(df, use_container_width=True)

# SEKACJA DEBUGOWANIA - POKAŻE CO NAPRAWDĘ ZWRACA API RUPTELI
with st.expander("🛠️ Diagnostyka Ruptela API (Rozwiń, aby sprawdzić surowe dane)"):
    st.json(raw_debug)
