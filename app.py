import streamlit as st
import requests
import pandas as pd

# Konfiguracja widoku pod urządzenia mobilne
st.set_page_config(
    page_title="Koszty Floty - Ruptela",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🚛 Rozliczenie Kosztów Floty")
st.caption("Integracja z telematyką Ruptela GPS")

# --- KROK 1: POBIERANIE KLUCZA API Z SECRETS ---
# Klucz API podasz bezpiecznie w panelu Streamlit Cloud (Settings -> Secrets)
RUPTELA_API_KEY = st.secrets.get("RUPTELA_API_KEY", "")

# --- KROK 2: FUNKCJA POBIERAJĄCA DANE Z RUPTELA API ---
@st.cache_data(ttl=300)  # Odświeżanie danych co 5 minut
def fetch_ruptela_data(api_key):
    if not api_key:
        return None
    
    # Przykładowe zapytanie do REST API TrustTrack / Ruptela
    url = "https://api.trusttrack.io/v1/vehicles" # Zmień na właściwy endpoint w zależności od wersji API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"Błąd API Ruptela (Kod {response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"Nie udało się połączyć z API: {e}")
        return None

# --- KROK 3: POBRANIE DANYCH LUB WYGENEROWANIE DANYCH TESTOWYCH ---
raw_data = fetch_ruptela_data(RUPTELA_API_KEY)

if not RUPTELA_API_KEY:
    st.info("💡 Brak klucza `RUPTELA_API_KEY` w Secrets. Wyświetlam **dane demonstracyjne**.")

# Jeśli API jeszcze nie odpowiada lub brak klucza, podstawiamy przykładowe dane do podglądu UI
if not raw_data:
    df = pd.DataFrame([
        {"Pojazd": "Pojazd 01 (SCANIA)", "Dystans_km": 1420.5, "Spalanie_L": 397.7},
        {"Pojazd": "Pojazd 02 (VOLVO)", "Dystans_km": 980.0, "Spalanie_L": 264.6},
        {"Pojazd": "Pojazd 03 (MAN)", "Dystans_km": 1850.2, "Spalanie_L": 536.5},
    ])
else:
    # Przemapowanie rzeczywistej odpowiedzi z API na DataFrame
    # (Dostosuj nazwy pól po pierwszym uderzeniu w API)
    df = pd.DataFrame(raw_data)

# --- KROK 4: PARAMETRY KOSZTOWE (INPUTY UŻYTKOWNIKA) ---
st.subheader("⚙️ Parametry kosztowe")
col_p1, col_p2 = st.columns(2)

with col_p1:
    cena_paliwa = st.number_input("Cena ON za litr (PLN netto):", value=6.20, step=0.05, format="%.2f")
with col_p2:
    oplaty_drogowe = st.number_input("Inne koszty / e-TOLL (PLN):", value=450.0, step=50.0)

# --- KROK 5: KALKULACJA KOSZTÓW ---
df["Koszt_Paliwa"] = df["Spalanie_L"] * cena_paliwa
df["Średnie_Spalanie_100km"] = (df["Spalanie_L"] / df["Dystans_km"]) * 100
df["Koszt_na_KM"] = df["Koszt_Paliwa"] / df["Dystans_km"]

suma_km = df["Dystans_km"].sum()
suma_litry = df["Spalanie_L"].sum()
suma_koszt_paliwa = df["Koszt_Paliwa"].sum()
calkowity_koszt = suma_koszt_paliwa + oplaty_drogowe
sredni_koszt_km = calkowity_koszt / suma_km if suma_km > 0 else 0

# --- KROK 6: WSKAŹNIKI PODSUMOWUJĄCE (KPI) ---
st.divider()
st.subheader("📊 Podsumowanie floty")

kpi1, kpi2 = st.columns(2)
kpi3, kpi4 = st.columns(2)

kpi1.metric("Łączny Dystans", f"{suma_km:,.1f} km".replace(",", " "))
kpi2.metric("Zużyte Paliwo", f"{suma_litry:,.1f} L".replace(",", " "))
kpi3.metric("Łączny Koszt", f"{calkowity_koszt:,.2f} PLN".replace(",", " "))
kpi4.metric("Koszt na 1 km", f"{sredni_koszt_km:.2f} PLN/km")

# --- KROK 7: TABELA DANYCH I WYKRES ---
st.divider()
st.subheader("📋 Zestawienie wg pojazdów")

# Tabela dostosowana pod wyświetlanie na telefonie
st.dataframe(
    df[["Pojazd", "Dystans_km", "Spalanie_L", "Średnie_Spalanie_100km", "Koszt_Paliwa"]].style.format({
        "Dystans_km": "{:.1f} km",
        "Spalanie_L": "{:.1f} L",
        "Średnie_Spalanie_100km": "{:.2f} l/100km",
        "Koszt_Paliwa": "{:.2f} PLN"
    }),
    use_container_width=True
)

st.subheader("📈 Koszt paliwa wg pojazdu")
st.bar_chart(df.set_index("Pojazd")["Koszt_Paliwa"])
