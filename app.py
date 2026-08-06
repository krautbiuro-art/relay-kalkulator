import pytz

# Zastąp funkcję get_vehicle_trips tą wersją:
@st.cache_data(ttl=60)
def get_vehicle_trips(api_key, vehicle_id, dt_from, dt_to):
    # Ruptela w panelu działa w czasie lokalnym (Europe/Warsaw)
    # Konwertujemy czas z interfejsu Streamlit na UTC, aby API nie ucinało 2 godzin
    local_tz = pytz.timezone("Europe/Warsaw")
    
    dt_from_loc = local_tz.localize(dt_from)
    dt_to_loc = local_tz.localize(dt_to)
    
    dt_from_utc = dt_from_loc.astimezone(pytz.utc)
    dt_to_utc = dt_to_loc.astimezone(pytz.utc)
    
    from_str = dt_from_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_str = dt_to_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = f"https://api.fm-track.com/objects/{vehicle_id}/trips?version=1&from_datetime={from_str}&to_datetime={to_str}&api_key={api_key}"
    
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            res_data = resp.json()
            trips_list = res_data.get("trips", []) if isinstance(res_data, dict) else []
            
            if not trips_list:
                return 0.0, 0.0
            
            total_distance_m = 0.0
            total_fuel_can = 0.0
            has_can_fuel = False
            
            for trip in trips_list:
                # Sumujemy mileage (w metrach)
                dist_m = trip.get("mileage", 0.0)
                if dist_m:
                    total_distance_m += float(dist_m)
                
                fuel = trip.get("fuel_consumed", trip.get("fuel", trip.get("fuel_used", None)))
                if fuel is not None:
                    total_fuel_can += float(fuel)
                    has_can_fuel = True
            
            total_distance_km = total_distance_m / 1000.0
            return total_distance_km, (total_fuel_can if has_can_fuel else 0.0)
        return 0.0, 0.0
    except Exception:
        return 0.0, 0.0
