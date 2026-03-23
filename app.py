import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Orbital SIGINT Console", layout="wide")

st.title("Orbital SIGINT Console")
st.caption("Aerospace activity dashboard for launches, sensitive missions, failures, and satellite monitoring.")

# -----------------------------
# Helpers
# -----------------------------
def safe_text(value):
    return "" if value is None else str(value)

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
            "lat": pd.to_numeric(pad.get("latitude"), errors="coerce"),
            "lon": pd.to_numeric(pad.get("longitude"), errors="coerce"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["net"] = pd.to_datetime(df["net"], utc=True, errors="coerce")
        df = df.sort_values("net")
    return df


@st.cache_data(ttl=300)
def get_recent_launches():
    url = "https://ll.thespacedevs.com/2.2.0/launch/previous/?limit=60&mode=detailed"
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
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["net"] = pd.to_datetime(df["net"], utc=True, errors="coerce")
        df = df.sort_values("net", ascending=False)
    return df


# -----------------------------
# Load data
# -----------------------------
launch_error = None
recent_launch_error = None

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

# Satellite layer placeholder for now
satellite_error = "Live satellite feed temporarily unavailable."

# -----------------------------
# Derived data
# -----------------------------
failed_launches_df = pd.DataFrame()
sensitive_launches_df = pd.DataFrame()

if not recent_launches_df.empty:
    now_utc = pd.Timestamp.utcnow()

    # Recent failed launches in last 30 days
    if "status" in recent_launches_df.columns:
        failed_keywords = ["failure", "partial failure", "failed"]
        failed_mask = (
            recent_launches_df["status"]
            .fillna("")
            .str.lower()
            .apply(lambda x: any(word in x for word in failed_keywords))
        )
        failed_launches_df = recent_launches_df[failed_mask].copy()
        failed_launches_df = failed_launches_df[
            failed_launches_df["net"] >= now_utc - pd.Timedelta(days=30)
        ].copy()

    # Publicly labeled sensitive launches in last 90 days
    mission_series = recent_launches_df["mission_type"].fillna("").str.lower() if "mission_type" in recent_launches_df.columns else pd.Series("", index=recent_launches_df.index)
    provider_series = recent_launches_df["provider"].fillna("").str.lower() if "provider" in recent_launches_df.columns else pd.Series("", index=recent_launches_df.index)
    name_series = recent_launches_df["name"].fillna("").str.lower() if "name" in recent_launches_df.columns else pd.Series("", index=recent_launches_df.index)

    sensitive_keywords = [
        "government/top secret",
        "top secret",
        "government",
        "national security",
        "military",
        "reconnaissance",
        "surveillance",
        "classified",
    ]

    watched_providers = [
        "united launch alliance",
        "northrop grumman",
        "spacex",
        "rocket lab",
        "roscosmos",
    ]

    sensitive_mask = (
        mission_series.apply(lambda x: any(k in x for k in sensitive_keywords)) |
        name_series.apply(lambda x: any(k in x for k in sensitive_keywords)) |
        provider_series.apply(lambda x: any(k in x for k in watched_providers))
    )

    sensitive_launches_df = recent_launches_df[sensitive_mask].copy()
    sensitive_launches_df = sensitive_launches_df[
        sensitive_launches_df["net"] >= now_utc - pd.Timedelta(days=90)
    ].copy()

# -----------------------------
# Top status cards
# -----------------------------
st.subheader("System Status")

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("Upcoming Launches", len(launches_df))

with c2:
    st.metric("Recent Failed Launches", len(failed_launches_df))

with c3:
    st.metric("Sensitive Launches", len(sensitive_launches_df))

with c4:
    if launch_error:
        st.error("Launch Feed Offline")
    else:
        st.success("Launch Feed Online")

with c5:
    st.warning("Satellite Layer Offline")

st.divider()

# -----------------------------
# Main layout
# -----------------------------
left, right = st.columns([1.5, 1])

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
            fig_map.update_layout(height=520, margin=dict(l=0, r=0, t=50, b=0))
            st.plotly_chart(fig_map, use_container_width=True)

with right:
    st.subheader("Satellite Layer")

    st.info("Live satellite positions are temporarily unavailable. Launch monitoring remains active.")

    st.markdown("**Current status**")
    st.write("- Launch monitoring: online" if not launch_error else "- Launch monitoring: offline")
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
# Sensitive launches
# -----------------------------
st.subheader("Publicly Labeled Sensitive Launches")
st.caption("This section uses public labels and metadata only. It does not identify undisclosed or covert launches.")

if recent_launch_error:
    st.error(f"Recent launch history unavailable: {recent_launch_error}")
elif sensitive_launches_df.empty:
    st.info("No publicly labeled sensitive launches found in the last 90 days.")
else:
    sensitive_display = sensitive_launches_df[[
        "name",
        "net",
        "status",
        "provider",
        "rocket",
        "mission_type",
        "location_name",
    ]].copy()

    sensitive_display = sensitive_display.rename(columns={
        "name": "Launch",
        "net": "Time (UTC)",
        "status": "Status",
        "provider": "Provider",
        "rocket": "Rocket",
        "mission_type": "Mission Type",
        "location_name": "Location",
    })

    st.dataframe(sensitive_display, use_container_width=True, hide_index=True)

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
    next_launch_name = safe_text(launches_df.iloc[0]["name"]) if not launches_df.empty else "No launch available"
    next_launch_time = safe_text(launches_df.iloc[0]["net"]) if not launches_df.empty else "N/A"

    st.markdown(f"""
- **{len(launches_df)}** upcoming launch records are currently loaded.
- **{len(failed_launches_df)}** failed launches were found in the last 30 days.
- **{len(sensitive_launches_df)}** publicly labeled sensitive launches were found in the last 90 days.
- The **next scheduled launch** is **{next_launch_name}**.
- The next launch time is **{next_launch_time}**.
- The launch layer is operational.
- The satellite layer is temporarily offline and should be replaced with a fallback source or cached data.
""")
