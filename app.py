import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(
    page_title="Orbital SIGINT Console",
    layout="wide"
)

st.title("Orbital SIGINT Console")
st.caption("Aerospace activity dashboard for upcoming launches and satellite monitoring.")

# -----------------------------
# Data loading
# -----------------------------
@st.cache_data(ttl=300)
def get_upcoming_launches():
    url = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=15&mode=detailed"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    raw = response.json()["results"]

    rows = []
    for item in raw:
        pad = item.get("pad") or {}
        location = pad.get("location") or {}

        rows.append({
            "name": item.get("name"),
            "net": item.get("net"),
            "status": item.get("status", {}).get("name") if item.get("status") else None,
            "provider": item.get("launch_service_provider", {}).get("name") if item.get("launch_service_provider") else None,
            "rocket": item.get("rocket", {}).get("configuration", {}).get("name")
                if item.get("rocket") and item.get("rocket", {}).get("configuration") else None,
            "mission_type": item.get("mission", {}).get("type") if item.get("mission") else None,
            "location_name": location.get("name"),
            "country_code": location.get("country_code"),
            "lat": pad.get("latitude"),
            "lon": pad.get("longitude"),
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df["net"] = pd.to_datetime(df["net"], utc=True, errors="coerce")
        df = df.sort_values("net")

    return df


@st.cache_data(ttl=300)
def get_recent_launches():
    url = "https://ll.thespacedevs.com/2.2.0/launch/previous/?limit=40&mode=detailed"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    raw = response.json()["results"]

    rows = []
    for item in raw:
        pad = item.get("pad") or {}
        location = pad.get("location") or {}

        rows.append({
            "name": item.get("name"),
            "net": item.get("net"),
            "status": item.get("status", {}).get("name") if item.get("status") else None,
            "provider": item.get("launch_service_provider", {}).get("name") if item.get("launch_service_provider") else None,
            "rocket": item.get("rocket", {}).get("configuration", {}).get("name")
                if item.get("rocket") and item.get("rocket", {}).get("configuration") else None,
            "mission_type": item.get("mission", {}).get("type") if item.get("mission") else None,
            "location_name": location.get("name"),
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df["net"] = pd.to_datetime(df["net"], utc=True, errors="coerce")
        df = df.sort_values("net", ascending=False)

    return df


launch_error = None
recent_launch_error = None
satellite_error = "Live satellite feed temporarily unavailable."

try:
    launches_df = get_upcoming_launches()
except Exception as e:
    launches_df = pd.DataFrame()
    launch_error = str(e)

try:
    recent_launches_df = get_recent_launches()
except Exception as e:
    recent_launches_df = pd.DataFrame()
    recent_launch_error = str(e)

# -----------------------------
# Failed launches filter
# -----------------------------
failed_launches_df = pd.DataFrame()

if not recent_launches_df.empty and "status" in recent_launches_df.columns:
    failed_keywords = ["failure", "partial failure", "failed"]

    failed_launches_df = recent_launches_df[
        recent_launches_df["status"]
        .fillna("")
        .str.lower()
        .apply(lambda x: any(word in x for word in failed_keywords))
    ].copy()

    now_utc = pd.Timestamp.utcnow()
    failed_launches_df = failed_launches_df[
        failed_launches_df["net"] >= now_utc - pd.Timedelta(days=30)
    ].copy()

# -----------------------------
# Top status cards
# -----------------------------
st.subheader("System Status")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Upcoming Launches", len(launches_df))

with c2:
    st.metric("Recent Failed Launches", len(failed_launches_df))

with c3:
    if launch_error:
        st.error("Launch Feed Offline")
    else:
        st.success("Launch Feed Online")

with c4:
    st.warning("Satellite Layer Offline")

st.divider()

# -----------------------------
# Main layout
# -----------------------------
left, right = st.columns([1.4, 1])

with left:
    st.subheader("Launch Site Map")

    if launch_error:
        st.error("Launch map unavailable because the launch feed could not be loaded.")
    elif launches_df.empty:
        st.info("No launch data available right now.")
    else:
        map_df = launches_df.dropna(subset=["lat", "lon"]).copy()

        if map_df.empty:
            st.info("No launch coordinates available right now.")
        else:
            fig_map = px.scatter_geo(
                map_df,
                lat="lat",
                lon="lon",
                hover_name="name",
                hover_data=["provider", "rocket", "mission_type", "location_name", "net"],
                title="Upcoming Launch Locations"
            )
            fig_map.update_traces(marker=dict(size=10))
            fig_map.update_layout(height=500, margin=dict(l=0, r=0, t=50, b=0))
            st.plotly_chart(fig_map, use_container_width=True)

with right:
    st.subheader("Satellite Layer")

    st.info(
        "Live satellite positions are temporarily unavailable. "
        "Launch monitoring remains active."
    )

    st.markdown("**Current status**")
    st.write("- Launch monitoring: online")
    st.write("- Satellite tracking: offline")
    st.write("- Dashboard: operational")

    st.markdown("**Next improvement**")
    st.write("Add a fallback satellite source or cached snapshot.")

st.divider()

# -----------------------------
# Upcoming launches
# -----------------------------
st.subheader("Upcoming Launches")

if launch_error:
    st.error(f"Launch feed unavailable: {launch_error}")
elif launches_df.empty:
    st.info("No upcoming launches available.")
else:
    display_cols = [
        "name",
        "net",
        "status",
        "provider",
        "rocket",
        "mission_type",
        "location_name",
    ]

    nice_launches = launches_df[display_cols].copy()
    nice_launches = nice_launches.rename(columns={
        "name": "Launch",
        "net": "Time (UTC)",
        "status": "Status",
        "provider": "Provider",
        "rocket": "Rocket",
        "mission_type": "Mission Type",
        "location_name": "Location",
    })

    st.dataframe(nice_launches, use_container_width=True, hide_index=True)

st.divider()

# -----------------------------
# Recent failed launches
# -----------------------------
st.subheader("Recent Failed Launches")

if recent_launch_error:
    st.error(f"Recent launch history unavailable: {recent_launch_error}")
elif failed_launches_df.empty:
    st.success("No failed launches found in the last 30 days.")
else:
    failed_display = failed_launches_df[[
        "name",
        "net",
        "status",
        "provider",
        "rocket",
        "mission_type",
        "location_name",
    ]].copy()

    failed_display = failed_display.rename(columns={
        "name": "Launch",
        "net": "Time (UTC)",
        "status": "Status",
        "provider": "Provider",
        "rocket": "Rocket",
        "mission_type": "Mission Type",
        "location_name": "Location",
    })

    st.dataframe(failed_display, use_container_width=True, hide_index=True)

st.divider()

# -----------------------------
# Analyst summary
# -----------------------------
st.subheader("Analyst Summary")

if launch_error:
    st.markdown("""
- Launch feed is currently unavailable.
- Satellite layer is currently unavailable.
- Dashboard layout is online, but live data sources need attention.
""")
else:
    next_launch_name = launches_df.iloc[0]["name"] if not launches_df.empty else "No launch available"
    next_launch_time = launches_df.iloc[0]["net"] if not launches_df.empty else "N/A"

    st.markdown(f"""
- **{len(launches_df)}** upcoming launch records are currently loaded.
- **{len(failed_launches_df)}** failed launches were found in the last 30 days.
- The **next scheduled launch** is **{next_launch_name}**.
- The next launch time is **{next_launch_time}**.
- The launch layer is operational.
- The satellite layer is temporarily offline and should be replaced with a fallback source or cached data.
""")
