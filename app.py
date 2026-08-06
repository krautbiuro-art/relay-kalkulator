import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(page_title="System Floty Transportowej", layout="wide")

st.title("🚛 System Zarządzania Flotą (TMS)")

# 1. Pobranie klucza ze Streamlit Secrets
try:
    RUPTELA_API_KEY = st.secrets["RUPTELA_API_KEY"]
except Exception:
    st.error("⚠️ Brak klucza API w Streamlit Secrets! Dodaj 'RUPTELA_API_KEY' w ustawieniach aplikacji.")
    RUPTELA_API_KEY = ""

# Prawidłowy punkt końcowy API Ruptela (TrustTrack)
RUPTELA_API_URL = "https://trusttrack.ruptela.com/api/v1/vehicles"

def get_ruptela_data():
    if not RUPTELA_API_KEY:
        return []
    
    headers = {
        "Authorization": f"Bearer {RUPTELA_API_KEY}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(RUPTELA_API_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            vehicles_list = []
            
            items = data.get("data", data) if isinstance(data, dict) else data
            
            if isinstance(items, list):
                for item in items:
                    loc = item.get("last_location", {}) or item
                    vehicles_list.append({
                        "id": item.get("plate_number") or item.get("title") or f"Pojazd {item.get('id')}",
                        "driver": item.get("driver_name", "Brak danych"),
                        "lat": loc.get("latitude") or loc.get("lat"),
                        "lon": loc.get("longitude") or loc.get("lng") or loc.get("lon"),
                        "speed": loc.get("speed", 0),
                        "status": "W trasie" if loc.get("speed", 0) > 0 else "Postój"
                    })
            return vehicles_list
        else:
            st.warning(f"⚠️ Problem z API Ruptela (Kod: {response.status_code}): {response.text}")
            return []
            
    except Exception as e:
        st.error(f"❌ Błąd połączenia z API: {e}")
        return []

# Pobranie danych
vehicles = get_ruptela_data()

# Zakładki aplikacji
tab1, tab2, tab3 = st.tabs(["🗺️ Mapa na żywo (GPS)", "📊 Wykaz Floty", "💰 Koszty i Paliwo"])

with tab1:
    st.subheader("Lokalizacja pojazdów na żywo")
    
    if vehicles:
        valid_vehicles = [v for v in vehicles if v["lat"] is not None and v["lon"] is not None]
        
        if valid_vehicles:
            avg_lat = valid_vehicles[0]["lat"]
            avg_lon = valid_vehicles[0]["lon"]
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=7)
            
            for v in valid_vehicles:
                color = "green" if v["speed"] > 0 else "red"
                popup_text = f"<b>Pojazd:</b> {v['id']}<br><b>Kierowca:</b> {v['driver']}<br><b>Prędkość:</b> {v['speed']} km/h"
                folium.Marker(
                    [v["lat"], v["lon"]],
                    popup=popup_text,
                    tooltip=v["id"],
                    icon=folium.Icon(color=color, icon="truck", prefix="fa")
                ).add_to(m)
                
            st_folium(m, width=1200, height=500)
        else:
            st.info("Pobrano pozycje z Ruptela, ale pojazdy nie posiadają przypisanych współrzędnych GPS.")
    else:
        st.info("Brak aktywnych pojazdów lub oczekiwanie na odpowiedź z API...")

with tab2:
    st.subheader("Status floty")
    if vehicles:
        df_vehicles = pd.DataFrame(vehicles)
        st.dataframe(df_vehicles, use_container_width=True)
    else:
        st.write("Brak danych do wyświetlenia.")

with tab3:
    st.subheader("Rejestracja wydatków")
    col1, col2 = st.columns(2)
    with col1:
        pojazd_list = [v["id"] for v in vehicles] if vehicles else ["Brak aut"]
        pojazd = st.selectbox("Wybierz pojazd", pojazd_list)
        koszt = st.number_input("Kwota (PLN)", min_value=0.0, step=10.0)
        kategoria = st.selectbox("Kategoria", ["Paliwo", "Serwis/Naprawa", "Opłaty drogowe", "Inne"])
        if st.button("Zapisz wydatek"):
            st.success(f"Dodano wydatek {koszt} PLN dla {pojazd}")
