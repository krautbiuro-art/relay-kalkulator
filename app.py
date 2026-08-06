import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Diagnostyka Ruptela", page_icon="🔍", layout="wide")

st.title("🔍 Diagnostyka API Ruptela - Pobieranie Tras")

API_KEY = st.secrets.get("RUPTELA_API_KEY", "")

if not API_KEY:
    st.error("❌ Brak klucza RUPTELA_API_KEY w Secrets!")
    st.stop()

# 1. Pobieranie listy aut
@st.cache_data(ttl=300)
def get_vehicles(api_key):
    url = f"https://api.fm-track.com/objects?version=1&api_key={api_key}"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else []

vehicles = get_vehicles(API_KEY)

if not vehicles:
    st.error("Brak pojazdów.")
    st.stop()

v_options = {v.get("name"): v.get("id") for v in vehicles}
selected_name = st.selectbox("Wybierz pojazd do testu:", list(v_options.keys()))
selected_id = v_options[selected_name]

# Wybór dat
col1, col2 = st.columns(2)
with col1:
    d_from = st.date_input("Od:", datetime.now() - timedelta(days=7))
with col2:
    d_to = st.date_input("Do:", datetime.now())

from_iso = d_from.strftime("%Y-%m-%dT00:00:00Z")
to_iso = d_to.strftime("%Y-%m-%dT23:59:59Z")

st.divider()
st.subheader("Testowanie endpointów tras dla wybranych dat:")

# TEST 1: Endpoint /trips (Raport przejazdów)
st.write("1. Test `/trips`:")
url_trips = f"https://api.fm-track.com/objects/{selected_id}/trips?version=1&from={from_iso}&to={to_iso}&api_key={API_KEY}"
res_trips = requests.get(url_trips)
st.caption(f"Status kod: {res_trips.status_code}")
if res_trips.status_code == 200:
    st.json(res_trips.json())
else:
    st.write(res_trips.text)

# TEST 2: Endpoint /reports/trips
st.write("2. Test `/reports/trips`:")
url_rep = f"https://api.fm-track.com/reports/trips?version=1&object_id={selected_id}&from={from_iso}&to={to_iso}&api_key={API_KEY}"
res_rep = requests.get(url_rep)
st.caption(f"Status kod: {res_rep.status_code}")
if res_rep.status_code == 200:
    st.json(res_rep.json())
else:
    st.write(res_rep.text)
