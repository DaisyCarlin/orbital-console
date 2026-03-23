import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from skyfield.api import load

st.set_page_config(layout="wide")

st.title("Orbital SIGINT Console")

@st.cache_data(ttl=120)
def get_positions():

    tle_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
    satellites = load.tle_file(tle_url)

    ts = load.timescale()
    t = ts.now()

    rows = []

    for sat in satellites:
        geo = sat.at(t)
        sp = geo.subpoint()

        rows.append({
            "name": sat.name,
            "lat": sp.latitude.degrees,
            "lon": sp.longitude.degrees,
            "height_km": sp.elevation.km
        })

    return pd.DataFrame(rows)

positions_df = get_positions()

col1, col2 = st.columns(2)

with col1:
    st.metric("Satellites Tracked", len(positions_df))

fig = px.scatter_geo(
    positions_df,
    lat="lat",
    lon="lon",
    hover_name="name",
    title="Live Satellite Positions"
)

st.plotly_chart(fig, use_container_width=True)

@st.cache_data(ttl=300)
def get_launches():

    url = "https://ll.thespacedevs.com/2.3.0/launches/?limit=15"
    r = requests.get(url)
    data = r.json()["results"]

    rows = []

    for item in data:
        rows.append({
            "name": item.get("name"),
            "net": item.get("net"),
            "provider": item.get("launch_service_provider", {}).get("name")
        })

    return pd.DataFrame(rows)

launch_df = get_launches()

st.subheader("Upcoming Launches")
st.dataframe(launch_df)
