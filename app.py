import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Debug Ruptela", page_icon="🐛", layout="wide")
st.title("🐛 Podgląd odpowiedzi z Rupteli (/trips)")

API_KEY = st.secrets.get("RUPTELA_API_KEY", "")

# 1. Pobieramy obiekty
url_objects = f"https://api.fm-track.com/objects?version=1&api_key={API_KEY}"
res_obj = requests.get(url_objects)
vehicles = res_obj.json() if res_obj.status_code == 200 else []

if not vehicles:
    st.error("Brak pojazdów")
    st.stop()

# Wybór pojazdu do testu
v_options = {v.get("name"): v.get("id") for v in vehicles}
selected_name = st.selectbox("Wybierz pojazd:", list(v_options.keys()))
selected_id = v_options[selected_name]

col1, col2 = st.columns(2)
with col1:
    d_from = st.date_input("Od:", datetime.now() - timedelta(days=7))
with col2:
    d_to = st.date_input("Do:", datetime.now())

from_iso = d_from.strftime("%Y-%m-%dT00:00:00Z")
to_iso = d_to.strftime("%Y-%m-%dT23:59:59Z")

# Zapytanie z poprawnymi nazwami parametrów
url_trips = f"https://api.fm-track.com/objects/{selected_id}/trips?version=1&from_datetime={from_iso}&to_datetime={to_iso}&api_key={API_KEY}"

st.caption(f"Wywoływany URL: `{url_trips}`")

res_trips = requests.get(url_trips)
st.write(f"**Status Kod HTTP:** `{res_trips.status_code}`")

if res_trips.status_code == 200:
    data = res_trips.json()
    st.subheader("Otrzymana odpowiedź JSON:")
    st.json(data)
else:
    st.error("Błąd zapytania:")
    st.write(res_trips.text)
