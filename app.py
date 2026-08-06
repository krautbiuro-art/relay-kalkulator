import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, time

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

# --- 2. PRECYZYJNE OBLICZANIE ODOMETRU I PALIWA Z APEX TRAS ---
@st.cache_data(ttl=60)
def get_vehicle_exact_metrics(api_key, vehicle_id, dt_from, dt_to):
    from_str = dt_from.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_str = dt_to.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = f"https://api.fm-track.com/objects/{vehicle_id}/trips?version=1&from_datetime={from_str}&to_datetime={to_str}&api_key={api_key}"
    
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return 0.0, 0.0
            
        data = resp.json()
        trips = data.get("trips", []) if isinstance(data, dict) else []
        
        if not trips:
            return 0.0, 0.0
            
        # 1. POBRANIE WIRTUALNEGO ODOMETRU (ODCZYT CAN / GPS ODOMETER)
        # Szukamy odometru w pierwszym i ostatnim punkcie odcinka
        first_trip = trips[0]
        last_trip = trips[-1]
        
        start_odo = first_trip.get("start_odometer") or first_trip.get("odometer_start") or first_trip.get("odometer") or 0.0
        end_odo = last_trip.get("end_odometer") or last_trip.get("odometer_end") or last_trip.get("odometer") or 0.0
        
        start_odo = float(start_odo)
        end_odo = float(end_odo)
        
        # Jeśli odometry są wyrażone w metrach
        if start_odo > 1000000:
            start_odo /= 1000.0
        if end_odo > 1000000:
            end_odo /= 1000.0
            
        distance = 0.0
        if end_odo > start_odo and start_odo > 0:
            distance = end_odo - start_odo
        else:
            # Rezerwowo: suma dystansów z poszczególnych tras
            for t in trips:
                d = float(t.get("mileage", t.get("distance", 0.0)))
                distance += (d / 1000.0 if d > 10000 else d)
                
        # 2. SUMOWANIE ZUŻYCIA PALIWA
        total_fuel = 0.0
        for t in trips:
            f = float(t.get("fuel_consumed", t.get("fuel", t.get("fuel_used", 0.0))))
            total_fuel += f
            
        return distance, total_fuel
        
    except Exception:
        return 0.0, 0.0

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
srednia_norma = st.sidebar.number_input("Domyślna norma spalania (L/100km):", value=18.0, step=0.5)
oplaty_drogowe = st.sidebar.number_input("Dodatkowe koszty / e-TOLL (PLN):", value=0.0, step=50.0)

# --- PRZETWARZANIE DANYCH ---
flota_dane = []

with st.spinner("Pobieranie dokładnego kilometrażu z Ruptela API..."):
    if wybrany_id == "ALL":
        for v in vehicles:
            v_id = v.get("id")
            v_name = v.get("name", "Pojazd")
            dystans, spalanie = get_vehicle_exact_metrics(API_KEY, v_id, dt_od, dt_do)
            
            if spalanie == 0.0 and dystans > 0:
                spalanie = (dystans / 100.0) * srednia_norma
                
            flota_dane.append({
                "Pojazd": v_name,
                "Dystans_km": dystans,
                "Spalanie_L": spalanie
            })
    else:
        dystans, spalanie = get_vehicle_exact_metrics(API_KEY, wybrany_id, dt_od, dt_do)
        
        if spalanie == 0.0 and dystans > 0:
            spalanie = (dystans / 100.0) * srednia_norma
            
        flota_dane.append({
            "Pojazd": wybrane_auto_label,
            "Dystans_km": dystans,
            "Spalanie_L": spalanie
        })

df = pd.DataFrame(flota_dane)

# KONTROLA BRAKU DANYCH
if df.empty or df["Dystans_km"].sum() == 0:
    st.info(f"ℹ️ Brak zarejestrowanych tras w wybranym okresie ({dt_od.strftime('%d.%m.%Y %H:%M')} - {dt_do.strftime('%d.%m.%Y %H:%M')}). Upewnij się, że pojazdy wykonywały przejazdy w tym czasie.")
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
    st.subheader(f"📊 Wyniki za okres: {dt_od.strftime('%d.%m.%Y %H:%M')} - {dt_do.strftime('%d.%m.%Y %H:%M')}")
    
    k1, k2 = st.columns(2)
    k3, k4 = st.columns(2)
    
    k1.metric("Łączny Dystans", f"{suma_km:,.2f} km".replace(",", " "))
    k2.metric("Zużyte Paliwo", f"{suma_litry:,.2f} L".replace(",", " "))
    k3.metric("Łączny Koszt", f"{calkowity_koszt:,.2f} PLN".replace(",", " "))
    k4.metric("Koszt na 1 km", f"{sredni_koszt_km:.2f} PLN/km")

    # TABELA DANYCH
    st.divider()
    st.subheader("📋 Podsumowanie wg pojazdów")
    st.dataframe(
        df[["Pojazd", "Dystans_km", "Spalanie_L", "Średnie_l/100km", "Koszt_Paliwa"]].style.format({
            "Dystans_km": "{:.2f} km",
            "Spalanie_L": "{:.2f} L",
            "Średnie_l/100km": "{:.2f} l/100km",
            "Koszt_Paliwa": "{:.2f} PLN"
        }),
        use_container_width=True
    )
    
    st.subheader("📈 Podział kosztu paliwa")
    st.bar_chart(df.set_index("Pojazd")["Koszt_Paliwa"])
