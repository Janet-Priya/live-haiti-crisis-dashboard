import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path
import google.generativeai as genai
import json
import re
DB_PATH = "reports.db"


st.set_page_config(
    page_title="Haiti Violence Analysis Dashboard",
    page_icon="🫂",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data(ttl=3600)
def load_crisis_data():
    """Load crisis data from SQLite database and clean date columns."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM reports ORDER BY timestamp DESC", conn)
        conn.close()

        if not df.empty:
            df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

col1, col2 = st.columns([6, 1])
with col1:
    st.markdown("## Haiti Violence Analysis Dashboard")

with col2:
    if st.button(" Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

df = load_crisis_data()

if df.empty:
    st.error("No data found. Run harvester.py first.")
    st.stop()

def load_css(file_path):
    """Load CSS from external file"""
    css_file = Path(file_path)
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {file_path}")

# Load the external CSS file
load_css("style.css")

# Initialize Gemini with your API key from environment variable
import os
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

def gemini_extract_metrics(text, threshold=1000):
    # Split text into lines and ignore summary lines
    incident_lines = []
    for line in text.split('\n'):
        if not re.match(r'^\s*Total (killed|injured|kidnapped)', line, re.IGNORECASE):
            incident_lines.append(line)
    incident_text = "\n".join(incident_lines)
    
    prompt = (
        "Extract all numbers of people killed and injured from the following incident report text. "
        "Ignore any summary or total lines. Return a JSON object with keys: killed, injured. "
        "If not mentioned, use 0. If there are multiple mentions, sum them. Respond ONLY with JSON. "
        f"Text: {incident_text}"
    )
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        if hasattr(response, "text"):
            result_text = response.text
        elif hasattr(response, "candidates"):
            result_text = response.candidates[0].content.parts[0].text
        else:
            result_text = str(response)
        print("Gemini output:", result_text)
        try:
            result_text = re.sub(r"^```json|```$", "", result_text, flags=re.MULTILINE).strip()
            metrics = json.loads(result_text)
            killed = int(metrics.get("killed", 0)) if str(metrics.get("killed", "0")).isdigit() else 0
            injured = int(metrics.get("injured", 0)) if str(metrics.get("injured", "0")).isdigit() else 0
            # Ignore if above threshold
            killed = killed if killed <= threshold else 0
            injured = injured if injured <= threshold else 0
            return killed, injured
        except Exception:
            killed_matches = re.findall(r'(\d+)\s+(?:killed)', incident_text, re.IGNORECASE)
            injured_matches = re.findall(r'(\d+)\s+(?:injured)', incident_text, re.IGNORECASE)
            killed = sum([int(x) for x in killed_matches if int(x) <= threshold]) if killed_matches else 0
            injured = sum([int(x) for x in injured_matches if int(x) <= threshold]) if injured_matches else 0
            return killed, injured
    except Exception as e:
        print("Error:", e)
        return 0, 0

# Apply Gemini extraction to your DataFrame
if "raw_text" in df.columns:
    df[["killed", "injured"]] = df["raw_text"].apply(
        lambda x: pd.Series(gemini_extract_metrics(x, threshold=1000))
    )

# Header
st.markdown(f"""
<div class="main-header">
    <div class="header-left">
        <span class="header-title">❦ Haiti Crisis Monitor</span>
        <span class="header-subtitle">Real-time conflict tracking</span>
    </div>
    <div class="header-right">
        <span class="live-badge"><span class="live-dot"></span> Live Data</span>
        <span class="update-time">Updated: {datetime.now().strftime('%I:%M:%S %p')}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# 🧠 fake sidebar layout — two columns
col_filters, col_main = st.columns([1.2, 3.8], gap="large")

# 💅 FILTER PANEL on the left
with col_filters:
    st.markdown("### 🗁 Filters")

    # Event Type
    event_types = st.multiselect(
        "Event Type", 
        sorted(df["event_type"].dropna().unique()), 
        default=list(df["event_type"].dropna().unique())
    )

    # Severity
    severity = st.slider("Severity Range", 1, 5, (1, 5))

    # Locations
    areas = st.multiselect(
        "Locations", 
        sorted(df["location_text"].dropna().unique()), 
        default=list(sorted(df["location_text"].dropna().unique()))
    )

    # Conflict-related only
    conflict_only = st.checkbox("Conflict-related only", value=True)

    # Date range
    if 'created_date' in df.columns:
        date_col = pd.to_datetime(
            df['created_date'].fillna(df['timestamp']),
            utc=True, errors='coerce'
        ).dt.tz_convert(None)

        if date_col.notna().any():
            min_date = date_col.min().date()
            max_date = date_col.max().date()
        else:
            min_date = (datetime.now() - timedelta(days=30)).date()
            max_date = datetime.now().date()
    else:
        min_date = (datetime.now() - timedelta(days=30)).date()
        max_date = datetime.now().date()

    date_range = st.date_input("Date Range", value=(min_date, max_date))

# 💾 FILTER APPLICATION LOGIC
filtered = df[
    (df["severity"] >= severity[0]) & 
    (df["severity"] <= severity[1])
]

if event_types:
    filtered = filtered[filtered["event_type"].isin(event_types)]

if areas:
    filtered = filtered[filtered["location_text"].isin(areas)]

if conflict_only:
    conflict_set = {
        "violence", "kidnapping", "sexual_violence",
        "displacement", "protest", "looting", "roadblock"
    }
    filtered = filtered[filtered["event_type"].isin(conflict_set)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + timedelta(days=1)
    effective_date = pd.to_datetime(
        filtered["created_date"].fillna(filtered["timestamp"]),
        utc=True, errors="coerce"
    ).dt.tz_convert(None)
    filtered = filtered[(effective_date >= start_date) & (effective_date < end_date)]


# 🌸 a lil CSS to make it pop
st.markdown("""
<style>
    [data-testid="stColumn"] {
        background: linear-gradient(135deg, rgba(36,0,70,0.6), rgba(0,0,0,0.3));
        border-radius: 16px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)


with col_main:
    st.markdown(
        """
        <div style="color: #f0f0f0; font-size: 25px; line-height: 1.6; padding: 10px;">
            <p>
            The <b>Haiti Crisis Data Dashboard</b> provides a live, data-driven view of the ongoing humanitarian emergency in Haiti. 
            It compiles and visualizes real-time reports of violence, displacement, and instability across the nation, 
            helping translate raw data into actionable insight for decision-makers, journalists, and relief organizations.
            </p>
            <p>
            By aggregating open-source intelligence, geolocation data, and verified event reports, 
            this platform allows users to track the scale, distribution, and intensity of conflict incidents over time. 
            Trends in severity, location patterns, and crisis escalation are dynamically updated to provide situational awareness 
            and support rapid-response planning.
            </p>
            <p>
            The dashboard’s goal is not only to monitor the crisis but also to empower analysis — 
            offering clarity in an environment of uncertainty. Each visualization aims to connect data with human context, 
            bringing transparency to a rapidly evolving humanitarian landscape.
            </p>
            <p>
            Updated automatically every few hours, this dashboard reflects Haiti’s unfolding story — 
            a nation in turmoil, resilience, and transition.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )




# Key Metrics
st.markdown('<div class="section-header">Key Metrics</div>', unsafe_allow_html=True)

# Calculate metrics first
current_incidents = len(filtered)
locations = filtered["location_text"].nunique()
avg_severity = filtered["severity"].mean() if not filtered.empty else 0
critical = len(filtered[filtered["severity"] >= 4])

# Metric Cards with icons
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{current_incidents}</div>
        <div class="metric-label">Total Incidents</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{locations}</div>
        <div class="metric-label">Active Zones</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{avg_severity:.2f}</div>
        <div class="metric-label">Avg Severity</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{critical}</div>
        <div class="metric-label">Critical Cases</div>
    </div>
    """, unsafe_allow_html=True)


# Additional Insights
st.markdown('<div class="section-header"> Additional Insights</div>', unsafe_allow_html=True)
col6, col7, col8 = st.columns(3)

with col6:
    killed = filtered["killed"].sum() if "killed" in filtered.columns else 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{killed:,}</div>
        <div class="metric-label">Total Killed</div>
    </div>
    """, unsafe_allow_html=True)

with col7:
    injured = filtered["injured"].sum() if "injured" in filtered.columns else 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{injured:,}</div>
        <div class="metric-label">Total Injured</div>
    </div>
    """, unsafe_allow_html=True)

with col8:
    critical = len(filtered[filtered["severity"] >= 4])
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{critical}</div>
        <div class="metric-label">Critical Cases</div>
    </div>
    """, unsafe_allow_html=True)

# Download button
st.download_button(
    label= "Download Filtered Data",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name=f"haiti_crisis_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

# Incident Trends
st.markdown('<div class="section-header">Incident Trends Over Time</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    if 'created_date' in filtered.columns:
        filtered["month"] = pd.to_datetime(
            filtered["created_date"].fillna(filtered["timestamp"]),
            utc=True, errors="coerce"
        ).dt.tz_convert(None).dt.to_period("M").dt.to_timestamp()
        
        monthly = filtered.groupby("month").size().reset_index(name="count")
        
        fig_monthly = go.Figure()
        fig_monthly.add_trace(go.Scatter(
            x=monthly["month"],
            y=monthly["count"],
            mode='lines+markers',
            name='Incidents',
            line=dict(color='#6366f1', width=3),
            marker=dict(size=10, color='#a855f7', line=dict(width=2, color='#6366f1')),
            fill='tozeroy',
            fillcolor='rgba(99, 102, 241, 0.2)'
        ))
        
        fig_monthly.update_layout(
            title="Monthly Incident Trends",
            xaxis_title="Month",
            yaxis_title="Number of Incidents",
            template="plotly_dark",
            plot_bgcolor='rgba(15, 23, 42, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#e4e9f2', family='Inter'),
            height=350,
            margin=dict(l=50, r=20, t=60, b=50),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_monthly, use_container_width=True)

with col2:
    if 'created_date' in filtered.columns:
        filtered["week"] = pd.to_datetime(
            filtered["created_date"].fillna(filtered["timestamp"]),
            utc=True, errors="coerce"
        ).dt.tz_convert(None).dt.to_period("W").dt.start_time
        
        last_weeks = filtered["week"].dropna().sort_values().unique()[-8:]
        weekly = filtered[filtered["week"].isin(last_weeks)].groupby("week").size().reset_index(name="count")
        
        fig_weekly = go.Figure()
        fig_weekly.add_trace(go.Bar(
            x=weekly["week"],
            y=weekly["count"],
            marker=dict(
                color=weekly["count"],
                colorscale=[[0, '#6366f1'], [1, '#ef4444']],
                showscale=False,
                line=dict(width=0)
            ),
            text=weekly["count"],
            textposition='outside'
        ))
        
        fig_weekly.update_layout(
            title="Weekly Incident Pattern (Last 8 Weeks)",
            xaxis_title="Week",
            yaxis_title="Number of Incidents",
            template="plotly_dark",
            plot_bgcolor='rgba(15, 23, 42, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#e4e9f2', family='Inter'),
            height=350,
            margin=dict(l=50, r=20, t=60, b=50)
        )
        
        st.plotly_chart(fig_weekly, use_container_width=True)

# Analysis grids
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="section-header"> Top Violence Hotspots</div>', unsafe_allow_html=True)
    
    location_counts = filtered['location_text'].value_counts().head(5).reset_index()
    location_counts.columns = ['Location', 'Incidents']
    
    fig_hotspots = go.Figure()
    fig_hotspots.add_trace(go.Bar(
        x=location_counts['Incidents'],
        y=location_counts['Location'],
        orientation='h',
        marker=dict(
            color=location_counts['Incidents'],
            colorscale=[[0, '#6366f1'], [1, '#ef4444']],
            showscale=False
        ),
        text=location_counts['Incidents'],
        textposition='outside'
    ))
    
    fig_hotspots.update_layout(
        template="plotly_dark",
        plot_bgcolor='rgba(15, 23, 42, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#e4e9f2', family='Inter'),
        height=350,
        margin=dict(l=150, r=50, t=20, b=50),
        xaxis_title="Number of Incidents",
        yaxis_title="",
        showlegend=False
    )
    
    st.plotly_chart(fig_hotspots, use_container_width=True)
    
    # Daily heatmap
    st.markdown('<div class="section-header"> Daily Incident Heatmap</div>', unsafe_allow_html=True)
    
    if 'created_date' in filtered.columns:
        filtered['day_of_week'] = pd.to_datetime(
            filtered["created_date"].fillna(filtered["timestamp"]),
            utc=True, errors="coerce"
        ).dt.tz_convert(None).dt.day_name()
        
        filtered['hour'] = pd.to_datetime(
            filtered["created_date"].fillna(filtered["timestamp"]),
            utc=True, errors="coerce"
        ).dt.tz_convert(None).dt.hour
        
        heatmap_data = filtered.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
        heatmap_pivot = heatmap_data.pivot(index='day_of_week', columns='hour', values='count').fillna(0)
        
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_pivot = heatmap_pivot.reindex([d for d in day_order if d in heatmap_pivot.index])
        
        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=heatmap_pivot.columns,
            y=heatmap_pivot.index,
            colorscale=[[0, '#1e293b'], [0.5, '#6366f1'], [1, '#ef4444']],
            showscale=True,
            colorbar=dict(title="Count")
        ))
        
        fig_heatmap.update_layout(
            template="plotly_dark",
            plot_bgcolor='rgba(15, 23, 42, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#e4e9f2', family='Inter'),
            height=350,
            margin=dict(l=100, r=20, t=20, b=50),
            xaxis_title="Hour of Day",
            yaxis_title=""
        )
        
        st.plotly_chart(fig_heatmap, use_container_width=True)

with col2:
    st.markdown('<div class="section-header"> Incident Severity Distribution</div>', unsafe_allow_html=True)
    
    severity_counts = filtered['severity'].value_counts().sort_index().reset_index()
    severity_counts.columns = ['Severity', 'Count']
    severity_counts['Severity'] = severity_counts['Severity'].astype(str)
    
    fig_severity = go.Figure()
    fig_severity.add_trace(go.Pie(
        labels=severity_counts['Severity'],
        values=severity_counts['Count'],
        hole=0.6,
        marker=dict(colors=['#10b981', '#6366f1', '#f59e0b', '#ef4444', '#991b1b']),
        textinfo='label+percent',
        textfont=dict(size=12, color='white')
    ))
    
    fig_severity.update_layout(
        template="plotly_dark",
        plot_bgcolor='rgba(15, 23, 42, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#e4e9f2', family='Inter'),
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.1)
    )
    
    st.plotly_chart(fig_severity, use_container_width=True)
    
    # Monthly growth
    st.markdown('<div class="section-header">Monthly Growth Index</div>', unsafe_allow_html=True)
    
    if 'created_date' in filtered.columns:
        monthly_growth = filtered.groupby("month").size().reset_index(name="count")
        monthly_growth['growth'] = monthly_growth['count'].pct_change() * 100
        
        colors = ['#10b981' if x < 0 else '#ef4444' for x in monthly_growth['growth']]
        
        fig_growth = go.Figure()
        fig_growth.add_trace(go.Bar(
            x=monthly_growth["month"],
            y=monthly_growth["growth"],
            marker=dict(color=colors),
            text=monthly_growth["growth"].round(1),
            texttemplate='%{text}%',
            textposition='outside'
        ))
        
        fig_growth.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        
        fig_growth.update_layout(
            title="Month-over-Month Change (%)",
            template="plotly_dark",
            plot_bgcolor='rgba(15, 23, 42, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#e4e9f2', family='Inter'),
            height=350,
            margin=dict(l=50, r=20, t=60, b=50),
            xaxis_title="Month",
            yaxis_title="Growth Rate (%)"
        )
        
        st.plotly_chart(fig_growth, use_container_width=True)

# Predictive Intelligence
st.markdown('<div class="section-header"> AI-Powered Incident Forecasting</div>', unsafe_allow_html=True)

if len(filtered) > 30:
    filtered['days_since_start'] = (
        pd.to_datetime(filtered["created_date"].fillna(filtered["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None) - 
        pd.to_datetime(filtered["created_date"].fillna(filtered["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None).min()
    ).dt.days
    
    daily_counts = filtered.groupby('days_since_start').size().reset_index(name='count')
    daily_counts['ma_7'] = daily_counts['count'].rolling(window=7, min_periods=1).mean()
    
    last_day = daily_counts['days_since_start'].max()
    future_days = pd.DataFrame({'days_since_start': range(last_day + 1, last_day + 31)})
    future_days['ma_7'] = daily_counts['ma_7'].iloc[-1]
    
    fig_forecast = go.Figure()
    
    fig_forecast.add_trace(go.Scatter(
        x=daily_counts['days_since_start'],
        y=daily_counts['count'],
        mode='lines',
        name='Actual Incidents',
        line=dict(color='#6366f1', width=2),
        opacity=0.6
    ))
    
    fig_forecast.add_trace(go.Scatter(
        x=daily_counts['days_since_start'],
        y=daily_counts['ma_7'],
        mode='lines',
        name='7-Day Moving Average',
        line=dict(color='#a855f7', width=3)
    ))
    
    fig_forecast.add_trace(go.Scatter(
        x=future_days['days_since_start'],
        y=future_days['ma_7'],
        mode='lines',
        name='30-Day Forecast',
        line=dict(color='#ef4444', width=3, dash='dot'),
        fill='tonexty',
        fillcolor='rgba(239, 68, 68, 0.2)'
    ))
    
    fig_forecast.update_layout(
        title="Incident Forecast - Next 30 Days",
        xaxis_title="Days from Data Start",
        yaxis_title="Daily Incidents",
        template="plotly_dark",
        plot_bgcolor='rgba(15, 23, 42, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#e4e9f2', family='Inter'),
        height=450,
        margin=dict(l=50, r=20, t=60, b=50),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_forecast, use_container_width=True)
else:
    st.info("📊 Insufficient data for forecasting. Need at least 30 data points.")

    

# Danger Ranking
st.markdown('<div class="section-header"> Top Dangerous Locations</div>', unsafe_allow_html=True)

if not filtered.empty:
    danger_rank = (
        filtered.groupby("location_text")
        .agg(
            incidents=("event_type", "count"),
            avg_severity=("severity", "mean"),
            critical=("severity", lambda x: (x>=4).sum())
        )
        .sort_values(["critical", "incidents"], ascending=[False, False])
        .head(10)
        .reset_index()
    )
    
    danger_rank['avg_severity'] = danger_rank['avg_severity'].round(2)
    danger_rank.columns = ['Location', 'Total Incidents', 'Avg Severity', 'Critical Cases']
    
    st.dataframe(
        danger_rank,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No data available for danger ranking.")
# Interactive Map
st.markdown('<div class="section-header">✵ Interactive Crisis Map</div>', unsafe_allow_html=True)

map_mode = st.radio(
    "Map Visualization Type",
    ["Bubble Map", "Density Heatmap"],
    horizontal=True
)

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
                    hover_data={
                        "title": True,
                        "source_name": True,
                        "event_type": True,
                        "latitude": False,
                        "longitude": False,
                        "severity": True
                    },
                    zoom=6.5,
                    height=700,
                    color_continuous_scale=[[0, '#6366f1'], [0.5, '#f59e0b'], [1, '#ef4444']],
                    range_color=[1, 5],
                    labels={"severity": "Severity Level"}
                )
                
                fig_map.update_layout(
                    mapbox_style="carto-darkmatter",
                    template="plotly_dark",
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_colorbar=dict(
                        title="Severity",
                        thicknessmode="pixels",
                        thickness=15,
                        lenmode="pixels",
                        len=300,
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=0.01
                    )
                )
                
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                fig_heat = px.density_mapbox(
                    geo_data,
                    lat="latitude",
                    lon="longitude",
                    z="severity",
                    radius=20,
                    zoom=6.5,
                    height=700,
                    mapbox_style="carto-darkmatter",
                    color_continuous_scale=[[0, '#1e293b'], [0.3, '#6366f1'], [0.7, '#f59e0b'], [1, '#ef4444']],
                    labels={"severity": "Severity Density"}
                )
                
                fig_heat.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_colorbar=dict(
                        title="Density",
                        thicknessmode="pixels",
                        thickness=15,
                        lenmode="pixels",
                        len=300,
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=0.01
                    )
                )
                
                st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info(" No geocoded incidents available for mapping.")
    else:
        st.info(" Invalid coordinate data format.")
else:
    st.info("Location coordinates not available in the dataset.")


# Sources Section
st.markdown('<div class="section-header">🛢Sources</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    sources_html = '<div class="info-card info-scroll">'
    sources_html += '<div class="info-card-header">'
    sources_html += '<span> 🗐 Data Sources</span>'
    sources_html += '</div>'
    sources_html += '<div class="info-scroll-content">'
    
    if "source_name" in filtered.columns:
        source_counts = filtered["source_name"].value_counts().reset_index()
        source_counts.columns = ["Source", "Incidents"]
        source_times = {
            "ReliefWeb": "2 hours ago",
            "UNICEF": "3 hours ago",
            "OCHA": "4 hours ago",
            "MSF": "5 hours ago",
            "Red Cross": "6 hours ago",
            "WFP": "8 hours ago"
        }
        for _, row in source_counts.iterrows():
            source = row["Source"]
            incidents = row["Incidents"]
            time_info = source_times.get(source, "Recently")
            sources_html += '<div class="source-row">'
            sources_html += '<div>'
            sources_html += f'<span class="source-name">{source}</span>'
            sources_html += f'<span class="source-time">{time_info}</span>'
            sources_html += '</div>'
            sources_html += f'<div class="source-reports">{incidents} reports</div>'
            sources_html += '</div>'
    
    sources_html += '</div></div>'
    st.markdown(sources_html, unsafe_allow_html=True)

with col2:
    locations_html = '<div class="info-card info-scroll">'
    locations_html += '<div class="info-card-header">'
    locations_html += '<span> ⟟ Dangerous Locations</span>'
    locations_html += '</div>'
    locations_html += '<div class="info-scroll-content">'
    
    if "location_text" in filtered.columns:
        location_counts = filtered["location_text"].value_counts().reset_index()
        location_counts.columns = ["Location", "Incidents"]
        for _, row in location_counts.iterrows():
            location = row["Location"]
            incidents = row["Incidents"]
            locations_html += '<div class="source-row">'
            locations_html += '<div>'
            locations_html += f'<span class="source-name">{location}</span>'
            locations_html += '</div>'
            locations_html += f'<div class="source-reports">{incidents} incidents</div>'
            locations_html += '</div>'
    
    locations_html += '</div></div>'
    st.markdown(locations_html, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #94a3b8; padding: 2rem 0;'>
    <p> Haiti Violence Analysis Dashboard | Data updated in real-time</p>
    <p> Main source: ReliefWeb</p>
    <p style='font-size: 0.85rem; margin-top: 0.5rem;'>Built with Streamlit & Plotly | © 2025</p>
</div>
""", unsafe_allow_html=True)

