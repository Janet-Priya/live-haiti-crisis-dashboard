import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

DB_PATH = "reports.db"

# =======================
# CONFIGURATION
# =======================
st.set_page_config(
    page_title="Haiti Violence Analysis Dashboard",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =======================
# DARK UI STYLING + FONTS
# =======================
st.markdown("""
<style>
    body, .stApp { 
        background: #181926 !important; 
        color: #e0e6ed; 
        font-family: 'Inter', system-ui, sans-serif; 
    }
    .main-header h1 { 
        font-size: 2.2rem; 
        font-weight: 700; 
        margin-bottom: .25rem; 
        color: #f6f7f9;
    }
    .main-header p { 
        color: #a5adcb; 
        margin-top: 0; 
    }
    .section-header { 
        font-size: 1.1rem; 
        font-weight: 600; 
        color: #f6f7f9; 
        margin: 2rem 0 1rem 0; 
        border-bottom: 1px solid #232946; 
        padding-bottom: .5rem; 
    }
    .metric-card { 
        background: #232946; 
        border: 1px solid #393e5c; 
        border-radius: 12px; 
        padding: 1.2rem 1rem; 
        margin: .5rem 0; 
        box-shadow: 0 1px 4px 0 #232946; 
        color: #e0e6ed;
    }
    .stDownloadButton button { 
        background: #232946; 
        border: 1px solid #393e5c; 
        color: #e0e6ed; 
    }
    .stRadio > div { color: #e0e6ed !important; }
    .stSlider > div { color: #e0e6ed !important; }
    .stMultiSelect > div { color: #e0e6ed !important; }
    .stDateInput > div { color: #e0e6ed !important; }
</style>
""", unsafe_allow_html=True)

# =======================
# DATA LOADING
# =======================
@st.cache_data
def load_crisis_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM reports ORDER BY timestamp DESC", conn)
        conn.close()
        if not df.empty:
            df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce')
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

df = load_crisis_data()

if df.empty:
    st.error("⚠️ No data found — run harvester.py first.")
    st.stop()

# =======================
# HEADER
# =======================
st.markdown("""
<div class="main-header">
    <h1>Haiti Violence Analysis Dashboard</h1>
    <p>Incident monitoring and trends — updated continuously</p>
</div>
""", unsafe_allow_html=True)

# =======================
# SIDEBAR FILTERS
# =======================
with st.sidebar:
    st.markdown("### 🔍 Filters")
    event_types = st.multiselect("Event Type", df["event_type"].dropna().unique(), default=list(df["event_type"].dropna().unique()))
    severity = st.slider("Severity Range", 1, 5, (1, 5))
    areas = st.multiselect("Locations", sorted(df["location_text"].dropna().unique()), default=list(sorted(df["location_text"].dropna().unique())))
    conflict_only = st.checkbox("Conflict-related only", value=True)

    # Date range using created_date (report date) when available, else timestamp
    base_created = pd.to_datetime(df["created_date"], utc=True, errors="coerce") if "created_date" in df.columns else None
    base_timestamp = pd.to_datetime(df["timestamp"], utc=True, errors="coerce") if "timestamp" in df.columns else None
    if base_created is not None and base_timestamp is not None:
        effective_series = base_created.fillna(base_timestamp)
    elif base_created is not None:
        effective_series = base_created
    else:
        effective_series = base_timestamp
    if effective_series is not None:
        effective_series = effective_series.dt.tz_convert(None)
        if effective_series.notna().any():
            min_date = effective_series.min().date()
            max_date = effective_series.max().date()
        else:
            today = pd.Timestamp.today().normalize().to_pydatetime().date()
            min_date = (pd.Timestamp(today) - pd.Timedelta(days=30)).date()
            max_date = today
    else:
        today = pd.Timestamp.today().normalize().to_pydatetime().date()
        min_date = (pd.Timestamp(today) - pd.Timedelta(days=30)).date()
        max_date = today
    date_range = st.date_input("Report Date Range", value=(min_date, max_date))

# Apply filters
filtered = df[(df["severity"] >= severity[0]) & (df["severity"] <= severity[1])]
if event_types:
    filtered = filtered[filtered["event_type"].isin(event_types)]
if areas:
    filtered = filtered[filtered["location_text"].isin(areas)]
if conflict_only:
    conflict_set = {"violence", "kidnapping", "sexual_violence", "displacement", "protest", "looting", "roadblock"}
    filtered = filtered[filtered["event_type"].isin(conflict_set)]

# Apply date range on created_date when present, else timestamp
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
    effective_date = pd.to_datetime(
        filtered["created_date"].fillna(filtered["timestamp"]),
        utc=True, errors="coerce"
    ).dt.tz_convert(None)
    filtered = filtered[(effective_date >= start_date) & (effective_date < end_date)]

# =======================
# METRICS + DOWNLOAD
# =======================
st.markdown('<div class="section-header">📊 Key Metrics</div>', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-card"><div style="font-size:2rem;font-weight:700;">{len(filtered):,}</div><div>Total Incidents</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div style="font-size:2rem;font-weight:700;">{filtered["location_text"].nunique():,}</div><div>Unique Locations</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div style="font-size:2rem;font-weight:700;">{round(filtered["severity"].mean(),2) if not filtered.empty else 0}</div><div>Avg Severity</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div style="font-size:2rem;font-weight:700;">{filtered["source_name"].nunique():,}</div><div>Sources</div></div>', unsafe_allow_html=True)

# Optional: Add more metrics if columns exist
metric_cols = st.columns(3)
with metric_cols[0]:
    if "fatalities" in filtered.columns:
        st.markdown(f'<div class="metric-card"><div style="font-size:1.5rem;font-weight:700;">{filtered["fatalities"].sum():,}</div><div>Fatalities</div></div>', unsafe_allow_html=True)
with metric_cols[1]:
    if "displaced_persons" in filtered.columns:
        st.markdown(f'<div class="metric-card"><div style="font-size:1.5rem;font-weight:700;">{filtered["displaced_persons"].sum():,}</div><div>Displaced Persons</div></div>', unsafe_allow_html=True)
with metric_cols[2]:
    if "event_type" in filtered.columns:
        sec_ops = filtered[filtered["event_type"].str.contains("security|operation", case=False, na=False)]
        st.markdown(f'<div class="metric-card"><div style="font-size:1.5rem;font-weight:700;">{len(sec_ops):,}</div><div>Security Operations</div></div>', unsafe_allow_html=True)

st.download_button(
    label="⬇️ Download Filtered Data",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="haiti_crisis_filtered.csv",
    mime="text/csv"
)

# =======================
# MONTHLY INCIDENT TRENDS
# =======================
st.markdown('<div class="section-header"> Monthly Incident Trends</div>', unsafe_allow_html=True)
if "created_date" in filtered.columns:
    filtered["report_month"] = pd.to_datetime(
        filtered["created_date"].fillna(filtered["timestamp"]),
        utc=True, errors="coerce"
    ).dt.tz_convert(None).dt.to_period("M").dt.to_timestamp()
    monthly = filtered.groupby("report_month").size().reset_index(name="count")
    fig_month = px.line(
        monthly, x="report_month", y="count", 
        title="Incident Reports Over the Past 12 Months", 
        markers=True,
        template="plotly_dark"
    )
    fig_month.update_traces(line_color="#e63946", marker_color="#e63946", fill='tozeroy', fillcolor="rgba(230,57,70,0.2)")
    fig_month.update_layout(
        xaxis_title="Month", 
        yaxis_title="Incidents",
        plot_bgcolor="#181926",
        paper_bgcolor="#181926",
        font_color="#e0e6ed"
    )
    st.plotly_chart(fig_month, use_container_width=True)

# =======================
# WEEKLY ANALYSIS (last 7 weeks)
# =======================
st.markdown('<div class="section-header"> Weekly Analysis</div>', unsafe_allow_html=True)
if "created_date" in filtered.columns:
    filtered["report_week"] = pd.to_datetime(
        filtered["created_date"].fillna(filtered["timestamp"]),
        utc=True, errors="coerce"
    ).dt.tz_convert(None).dt.to_period("W").dt.start_time
    last_weeks = filtered["report_week"].dropna().sort_values().unique()[-7:]
    weekly = filtered[filtered["report_week"].isin(last_weeks)].groupby("report_week").size().reset_index(name="count")
    fig_week = px.bar(
        weekly, x="report_week", y="count", 
        title="Recent 7-week Incident Pattern", 
        color="count", 
        color_continuous_scale="Blues",
        template="plotly_dark"
    )
    fig_week.update_layout(
        xaxis_title="Week", 
        yaxis_title="Incidents", 
        showlegend=False,
        plot_bgcolor="#181926",
        paper_bgcolor="#181926",
        font_color="#e0e6ed"
    )
    st.plotly_chart(fig_week, use_container_width=True)

# =======================
# EVENT TYPES PIE CHART
# =======================
st.markdown('<div class="section-header">Event Type Share</div>', unsafe_allow_html=True)
type_counts = filtered["event_type"].value_counts().reset_index()
type_counts.columns = ["Event Type", "Count"]
fig_pie = px.pie(
    type_counts, names="Event Type", values="Count", 
    title="Event Type Distribution", hole=0.4,
    template="plotly_dark"
)
fig_pie.update_traces(textinfo='percent+label')
fig_pie.update_layout(
    plot_bgcolor="#181926",
    paper_bgcolor="#181926",
    font_color="#e0e6ed"
)
st.plotly_chart(fig_pie, use_container_width=True)

# =======================
# MAP (Bubble + Heatmap toggle)
# =======================
st.markdown('<div class="section-header"> Crisis Map</div>', unsafe_allow_html=True)
map_mode = st.radio("Map Mode", ["Bubble Map", "Heatmap"], horizontal=True)

if "location_coords" in filtered.columns:
    coords = filtered["location_coords"].dropna().str.split(",", expand=True)
    if not coords.empty and coords.shape[1] == 2:
        filtered["latitude"] = pd.to_numeric(coords[0], errors="coerce")
        filtered["longitude"] = pd.to_numeric(coords[1], errors="coerce")

        geo_data = filtered.dropna(subset=["latitude", "longitude"])
        if not geo_data.empty:
            if map_mode == "Bubble Map":
                fig_map = px.scatter_mapbox(
                    geo_data,
                    lat="latitude",
                    lon="longitude",
                    color="severity",
                    size="severity",
                    hover_name="location_text",
                    hover_data=["title", "source_name"],
                    zoom=6,
                    height=600,
                    color_continuous_scale=[(0, "green"), (0.5, "yellow"), (1, "red")],
                    range_color=[1, 5]
                )
                fig_map.update_layout(
                    mapbox_style="carto-darkmatter", 
                    template="plotly_dark",
                    plot_bgcolor="#181926",
                    paper_bgcolor="#181926",
                    font_color="#e0e6ed"
                )
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                fig_heat = px.density_mapbox(
                    geo_data,
                    lat="latitude",
                    lon="longitude",
                    z="severity",
                    radius=15,
                    zoom=6,
                    height=600,
                    mapbox_style="carto-darkmatter",
                    color_continuous_scale="Reds",
                    template="plotly_dark"
                )
                fig_heat.update_layout(
                    plot_bgcolor="#181926",
                    paper_bgcolor="#181926",
                    font_color="#e0e6ed"
                )
                st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("No geocoded reports available for mapping.")

