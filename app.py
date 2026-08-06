import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Test API Ruptela", page_icon="🚛")

st.title("🚛 Integracja z API Ruptela")

# Pobranie klucza z Secrets
API_KEY = st.secrets.get("RUPTELA_API_KEY", "")

if not API_KEY:
    st.error("❌ Brak klucza `RUPTELA_API_KEY` w Secrets Streamlit Cloud!")
    st.stop()

# Funkcja pobierająca listę obiektów/pojazdów z API Rupteli
@st.cache_data(ttl=60)
def get_ruptela_objects(api_key):
    # Domyślny endpoint Ruptela/TrustTrack Object API
    url = f"https://api.fm-track.com/objects?version=1&api_key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"Błąd {response.status_code}: {response.text}"
    except Exception as e:
        return None, str(e)

st.write("Łączenie z serwerem Ruptela...")

data, error = get_ruptela_objects(API_KEY)

if error:
    st.error(f"Nie udało się pobrać danych z API: {error}")
else:
    st.success("✅ Pomyślnie połączono z API Ruptela!")
    
    # Wyświetlenie surowych danych JSON do weryfikacji struktury
    st.subheader("Otrzymana odpowiedź z API:")
    st.json(data)
