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
def get_vehicles_list(api_key):
    url = f"https://api.fm-track.com/objects?version=1&api_key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []

# --- 2. POBIERANIE DANYCH BEZPOŚREDNIO Z API RUPTELA ---
def get_vehicle_stats(api_key, vehicle_id, dt_from, dt_to):
    # Daty w formacie lokalnym bez sztucznego przesuwania stref (tak jak panel WWW)
    from_str = dt_from.strftime("%Y-%m-%dT%H:%M:%S")
    to_str = dt_to.strftime("%Y-%m-%dT%H:%M:%S")
    
    # Próba 1: Raport zbiorczy (najdokładniejszy, zgodny z panelem WWW)
    summary_url = f"https://api.fm-track.com/reports/summary?version=1&objects={vehicle_id}&from_datetime={from_str}&to_datetime={to_str}&api_key={api_key}"
    
    try:
        resp = requests.get(summary_url, timeout=15)
        if resp.status_code == 200:
            res = resp.json()
            # Parsowanie różnych struktur odpowiedzi z API Rupteli
            records = res.get("reports", []) or res.get("items", []) or res.get("objects", []) or res.get("data", [])
            
            if records:
                item = records[0]
                # Pobranie dystansu i paliwa
                dist = float(item.get("mileage", item.get("distance", item.get("virtual_mileage", 0.0))))
                fuel = float(item.get("fuel_consumed", item.get("fuel", item.get("fuel_used", 0.0))))
                
                # Jeśli dystans podany w metrach, przelicz na km
                if dist > 50000:
                    dist = dist / 1000.0
                    
                if dist > 0:
                    return dist, fuel
    except Exception:
        pass

    # Próba 2: Zapasowy odczyt z /trips (sumowanie + wyciąganie odometru)
    trips_url = f"https://api.fm-track.com/objects/{vehicle_id}/trips?version=1&from_datetime={from_str}&to_datetime={to_str}&api_key={api_key}"
    try:
        resp = requests.get(trips_url, timeout=15)
        if resp.status_code == 200:
            res_data = resp.json()
            trips_list = res_data.get("trips", []) if isinstance(res_data, dict) else []
            
            if not trips_list:
                return 0.0, 0.0
            
            total_dist_m = sum(float(t.get("mileage", 0.0)) for t in trips_list)
            total_fuel = sum(float(t.get("fuel_consumed", t.get("fuel", t.get("fuel_used", 0.0)) or 0.0)) for t in trips_list)
            
            return total_dist_m / 1000.0, total_fuel
        return 0.0, 0.0
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
srednia_norma = st.sidebar.number_input("Domyślna norma spalania (L/100km):", value=21.33, step=0.5)
oplaty_drogowe = st.sidebar.number_input("Dodatkowe koszty / e-TOLL (PLN):", value=0.0, step=50.0)

# --- PRZETWARZANIE DANYCH ---
flota_dane = []

with st.spinner("Pobieranie dokładnych danych z Ruptela API..."):
    if wybrany_id == "ALL":
        for v in vehicles:
            v_id = v.get("id")
            v_name = v.get("name", "Pojazd")
            dystans, spalanie = get_vehicle_stats(API_KEY, v_id, dt_od, dt_do)
            
            if spalanie == 0.0 and dystans > 0:
                spalanie = (dystans / 100.0) * srednia_norma
                
            flota_dane.append({
                "Pojazd": v_name,
                "Dystans_km": dystans,
                "Spalanie_L": spalanie
            })
    else:
        dystans, spalanie = get_vehicle_stats(API_KEY, wybrany_id, dt_od, dt_do)
        
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
    st.info(f"ℹ️ Brak zarejestrowanych tras w wybranym okresie ({dt_od.strftime('%d.%m.%Y %H:%M')} - {dt_do.strftime('%d.%m.%Y %H:%M')}).")
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
