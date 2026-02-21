import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Weather Anomaly Tracker", layout="wide")

# Auto-refresh every 10 minutes
if hasattr(st, "auto_refresh"):
    st.auto_refresh(interval=600_000)

st.title("Weather Anomaly Tracker")
st.caption("Monitoring extreme weather across 6 global cities every 2 hours.")

CSV_FILE = "data/weather_anomalies.csv"

@st.cache_data(ttl=600)
def load_data():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        df['processed_at'] = pd.to_datetime(df['processed_at'], utc=True)
        return df
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.info("No weather anomalies have been recorded yet. The pipeline checks every 6 hours.")
else:
    # ── Sidebar: simple filters ──────────────────────────────────────
    with st.sidebar:
        st.header("Filters")
        cities = st.multiselect("City", sorted(set(df["city"].unique()).union({"Athens"})), default=sorted(set(df["city"].unique()).union({"Athens"})))
        types = st.multiselect("Type", sorted(df["anomaly_type"].unique()), default=sorted(df["anomaly_type"].unique()))

    filtered = df[df["city"].isin(cities) & df["anomaly_type"].isin(types)]

    if filtered.empty:
        st.warning("No anomalies match your filters. Try adjusting the sidebar selections.")
    else:
        # ── Key numbers ──────────────────────────────────────────────
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Anomalies", len(filtered))
        c2.metric("Cities Affected", filtered["city"].nunique())
        c3.metric("Avg Temperature", f"{filtered['temperature_c'].mean():.1f} °C")

        st.divider()

        # ── Tabs for charts ──────────────────────────────────────────
        tab_temp, tab_wind, tab_types = st.tabs(["Temperature", "Wind Speed", "Anomaly Types"])

        with tab_temp:
            st.scatter_chart(
                filtered[["processed_at", "city", "temperature_c"]].sort_values("processed_at"),
                x="processed_at",
                y="temperature_c",
                color="city",
            )

        with tab_wind:
            st.scatter_chart(
                filtered[["processed_at", "city", "wind_speed_kmh"]].sort_values("processed_at"),
                x="processed_at",
                y="wind_speed_kmh",
                color="city",
            )

        with tab_types:
            counts = filtered["anomaly_type"].value_counts().rename_axis("Type").reset_index(name="Count")
            st.bar_chart(counts, x="Type", y="Count")

        st.divider()

        # ── Data table ───────────────────────────────────────────────
        with st.expander("View raw data", expanded=False):
            st.dataframe(
                filtered.sort_values("processed_at", ascending=False)
                .rename(columns={
                    "city": "City",
                    "temperature_c": "Temp (°C)",
                    "wind_speed_kmh": "Wind (km/h)",
                    "processed_at": "Recorded At",
                    "anomaly_type": "Type",
                }),
                width="stretch",
            )
