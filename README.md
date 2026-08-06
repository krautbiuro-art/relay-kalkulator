# 🚛 System Kontroli Kosztów Transportu (API Ruptela)

Aplikacja mobilna i webowa zbudowana w Pythonie (Streamlit) do monitorowania zużycia paliwa, dystansu oraz wyliczania kosztów eksploatacji floty na podstawie danych z telematyki Ruptela.

## 🚀 Funkcjonalności
- Automatyczne pobieranie danych telemetrycznych (paliwo, km) z API Ruptela / TrustTrack.
- Przeliczanie zużycia paliwa na realne koszty (PLN).
- Widok dostosowany do urządzeń mobilnych.

## 🛠️ Technologie
- **Python 3.x**
- **Streamlit** (interfejs aplikacji)
- **Pandas** (analiza danych)
- **Requests** (integracja z REST API)

## 🔒 Konfiguracja Secrets (Streamlit Cloud)
Do poprawnego działania wymagany jest klucz API w ustawieniach aplikacji Streamlit Cloud:

```toml
RUPTELA_API_KEY = "twój_klucz_api"
