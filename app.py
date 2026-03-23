import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from skyfield.api import EarthSatellite, load

st.set_page_config(layout="wide", page_title="Orbital SIGINT Console")

st.title("Orbital SIGINT Console")
st.caption("Live orbital positions and upcoming launches")

@st.cache_data(ttl=300)
def get_positions():
    urls = [
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
        "https://celestrak.org/NORAD/elements/stations.txt",
    ]

    tle_text = None
    last_error = None

    for url in urls:
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            tle_text = response.text
            break
        except Exception as e:
            last_error = str(e)

    if not tle_text:
        raise RuntimeError(f"Could not load satellite TLE data. Last error: {last_error}")

    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]

    satellites = []
    for i in range(0, len(lines), 3):
        if i + 2 < len(lines):
            name = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]
            satellites.append((name, line1, line2))

    ts = load.timescale()
    t = ts.now()

    rows = []
    for name, line1, line2 in satellites[:12]:
        try:
            sat = EarthSatellite(line1, line2, name, ts)
            geocentric = sat.at(t)
            subpoint = geocentric.subpoint()
            rows.append({
                "name": name,
                "lat": subpoint.latitude.degrees,
                "lon": subpoint.longitude.degrees,
                "height_km": round(subpoint.elevation.km, 1),
            })
        except Exception:
            continue

    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def get_launches():
    url = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=10&mode=detailed"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    raw = response.json()["results"]

    rows = []
    for item in raw:
        rows.append({
            "name": item.get("name"),
            "net": item.get("net"),
            "status": item.get("status", {}).get("name") if item.get("status") else None,
            "provider": item.get("launch_service_provider", {}).get("name") if item.get("launch_service_provider") else None,
            "rocket": item.get("rocket", {}).get("configuration", {}).get("name")
                if item.get("rocket") and item.get("rocket", {}).get("configuration") else None,
        })

    df = pd.DataFrame(rows)
    if not df.empty and "net" in df.columns:
        df["net"] = pd.to_datetime(df["net"], utc=True, errors="coerce")
        df = df.sort_values("net")
    return df

positions_df = pd.DataFrame()
launches_df = pd.DataFrame()

satellite_error = None
launch_error = None

with st.spinner("Loading satellite positions..."):
    try:
        positions_df = get_positions()
    except Exception as e:
        satellite_error = str(e)

with st.spinner("Loading upcoming launches..."):
    try:
        launches_df = get_launches()
    except Exception as e:
        launch_error = str(e)

c1, c2 = st.columns(2)
c1.metric("Satellites tracked", len(positions_df))
c2.metric("Upcoming launches", len(launches_df))

st.subheader("Live Satellite Map")
if satellite_error:
    st.error(f"Satellite feed unavailable right now: {satellite_error}")
elif positions_df.empty:
    st.warning("No satellite positions loaded.")
else:
    fig = px.scatter_geo(
        positions_df,
        lat="lat",
        lon="lon",
        hover_name="name",
        hover_data=["height_km"],
        title="Current Satellite Positions"
    )
    fig.update_traces(marker=dict(size=8))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Upcoming Launches")
if launch_error:
    st.error(f"Launch feed unavailable right now: {launch_error}")
elif launches_df.empty:
    st.warning("No launch data loaded.")
else:
    st.dataframe(launches_df, use_container_width=True)
