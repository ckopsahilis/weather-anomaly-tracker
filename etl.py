import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import datetime, timezone
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
CITIES = {
    "New York": {"lat": 40.7143, "lon": -74.006},
    "Tokyo": {"lat": 35.6895, "lon": 139.6917},
    "London": {"lat": 51.5085, "lon": -0.1257},
    "Cairo": {"lat": 30.0626, "lon": 31.2497},
    "Sydney": {"lat": -33.8678, "lon": 151.2073},
    "Athens": {"lat": 37.9838, "lon": 23.7275}
}
DATA_FILE = "data/weather_anomalies.csv"
DEDUP_THRESHOLD_SECONDS = 300  # ignore runs within 5 minutes of last run

def _get_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def fetch_weather(session, lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m"
    response = session.get(url, timeout=10)
    response.raise_for_status()
    return response.json()["current"]

def is_anomaly(temp, wind):
    return temp > 35 or temp < -5 or wind > 30

def _last_processed_at():
    """Return the most recent processed_at timestamp from the CSV, or None."""
    if os.path.exists(DATA_FILE):
        try:
            existing = pd.read_csv(DATA_FILE)
            if not existing.empty:
                return pd.to_datetime(existing["processed_at"]).max()
        except Exception:
            pass
    return None

def main():
    now = datetime.now(timezone.utc)
    processed_at = now.isoformat()

    # Deduplication guard
    last_ts = _last_processed_at()
    if last_ts is not None:
        elapsed = (now - last_ts.to_pydatetime().replace(tzinfo=timezone.utc)).total_seconds()
        if 0 <= elapsed < DEDUP_THRESHOLD_SECONDS:
            logger.warning("Skipping run — only %d s since last run (threshold: %d s).", elapsed, DEDUP_THRESHOLD_SECONDS)
            return

    session = _get_session()
    anomalies = []

    for city, coords in CITIES.items():
        try:
            weather = fetch_weather(session, coords["lat"], coords["lon"])
            temp = weather["temperature_2m"]
            wind = weather["wind_speed_10m"]
            
            if is_anomaly(temp, wind):
                types = []
                if temp > 35:
                    types.append("High Temp")
                if temp < -5:
                    types.append("Low Temp")
                if wind > 30:
                    types.append("High Wind")

                anomalies.append({
                    "city": city,
                    "temperature_c": temp,
                    "wind_speed_kmh": wind,
                    "processed_at": processed_at,
                    "anomaly_type": " + ".join(types)
                })
        except Exception as e:
            logger.error("Error fetching data for %s: %s", city, e)

    if anomalies:
        df = pd.DataFrame(anomalies)
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        # Append to CSV if it exists, otherwise create it
        if os.path.exists(DATA_FILE):
            df.to_csv(DATA_FILE, mode='a', header=False, index=False)
        else:
            df.to_csv(DATA_FILE, index=False)
        
        logger.info("Logged %d anomalies successfully.", len(anomalies))
    else:
        logger.info("No anomalies detected.")

if __name__ == "__main__":
    main()
