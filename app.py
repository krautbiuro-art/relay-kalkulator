import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(page_title="System Floty Transportowej", layout="wide")

st.title("🚛 System Zarządzania Flotą (TMS)")

# Ustawienia API Ruptela (Wpisz swój klucz / token)
RUPTELA_API_URL = "https://api.trusttrack.ruptela.com/v1/vehicles/locations"
RUPTELA_API_KEY = "TWÓJ_KLUCZ_API"

@st.cache_data(ttl=30)
def get_ruptela_data():
    headers = {"Authorization": f"Bearer {RUPTELA_API_KEY}"}
    try:
        response = requests.get(RUPTELA_API_URL, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    
    # Dane testowe (gdy API Ruptela nie jest podłączone)
    return [
        {"id": "PO-12345", "driver": "Jan Kowalski", "lat": 52.2297, "lon": 21.0122, "speed": 68, "status": "W trasie"},
        {"id": "KR-98765", "driver": "Piotr Nowak", "lat": 50.0647, "lon": 19.9450, "speed": 0, "status": "Postój"},
        {"id": "DW-55555", "driver": "Tomasz Wiśniewski", "lat": 51.1079, "lon": 17.0385, "speed": 82, "status": "W trasie"}
    ]

vehicles = get_ruptela_data()

# Zakładki jak we Fleetbase
tab1, tab2, tab3 = st.tabs(["🗺️ Mapa na żywo (GPS)", "📊 Wykaz Floty i Kierowców", "💰 Koszty i Paliwo"])

with tab1:
    st.subheader("Lokalizacja pojazdów na żywo")
    
    # Tworzenie mapy
    m = folium.Map(location=[52.0, 19.0], zoom_start=6)
    
    for v in vehicles:
        color = "green" if v["speed"] > 0 else "red"
        popup_text = f"<b>Pojazd:</b> {v['id']}<br><b>Kierowca:</b> {v['driver']}<br><b>Prędkość:</b> {v['speed']} km/h"
        folium.Marker(
            [v["lat"], v["lon"]],
            popup=popup_text,
            tooltip=v["id"],
            icon=folium.Icon(color=color, icon="truck", prefix="fa")
        ).add_to(m)
        
    st_folium(m, width=1200, height=500)

with tab2:
    st.subheader("Status floty")
    df_vehicles = pd.DataFrame(vehicles)
    st.dataframe(df_vehicles, use_container_width=True)

with tab3:
    st.subheader("Rejestracja wydatków")
    col1, col2 = st.columns(2)
    with col1:
        pojazd = st.selectbox("Wybierz pojazd", [v["id"] for v in vehicles])
        koszt = st.number_input("Kwota (PLN)", min_value=0.0, step=10.0)
        kategoria = st.selectbox("Kategoria", ["Paliwo", "Serwis/Naprawa", "Opłaty drogowe", "Inne"])
        if st.button("Zapisz wydatek"):
            st.success(f"Dodano wydatek {koszt} PLN dla {pojazd}")
