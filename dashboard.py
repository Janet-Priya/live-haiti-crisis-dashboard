import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path

DB_PATH = "reports.db"

# Page configuration
st.set_page_config(
    page_title="Haiti Violence Analysis Dashboard",
    page_icon="🫂",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load external CSS
def load_css(file_path):
    """Load CSS from external file"""
    css_file = Path(file_path)
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {file_path}")

# Load the external CSS file
load_css("style.css")

# Data loading
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
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

df = load_crisis_data()

if df.empty:
    st.error("No data found. Run harvester.py first.")
    st.stop()

# Header
st.markdown("""
<div class="main-header">
    <h1> Haiti Violence Analysis Dashboard</h1>
    <p>Real-time conflict monitoring and predictive intelligence system</p>
</div>
""", unsafe_allow_html=True)

# Sidebar filters
with st.sidebar:
    st.markdown("### Filters")
    
    event_types = st.multiselect(
        "Event Type", 
        sorted(df["event_type"].dropna().unique()), 
        default=list(df["event_type"].dropna().unique())
    )
    
    severity = st.slider("Severity Range", 1, 5, (1, 5))
    
    areas = st.multiselect(
        "Locations", 
        sorted(df["location_text"].dropna().unique()), 
        default=list(sorted(df["location_text"].dropna().unique()))
    )
    
    conflict_only = st.checkbox("Conflict-related only", value=True)
    
    # Date range
    if 'created_date' in df.columns:
        date_col = pd.to_datetime(df['created_date'].fillna(df['timestamp']), utc=True, errors='coerce').dt.tz_convert(None)
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

# Apply filters
filtered = df[(df["severity"] >= severity[0]) & (df["severity"] <= severity[1])]

if event_types:
    filtered = filtered[filtered["event_type"].isin(event_types)]

if areas:
    filtered = filtered[filtered["location_text"].isin(areas)]

if conflict_only:
    conflict_set = {"violence", "kidnapping", "sexual_violence", "displacement", "protest", "looting", "roadblock"}
    filtered = filtered[filtered["event_type"].isin(conflict_set)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + timedelta(days=1)
    effective_date = pd.to_datetime(
        filtered["created_date"].fillna(filtered["timestamp"]),
        utc=True, errors="coerce"
    ).dt.tz_convert(None)
    filtered = filtered[(effective_date >= start_date) & (effective_date < end_date)]

# Calculate trends for metrics
prev_period_start = start_date - (end_date - start_date)
prev_filtered = df[
    (pd.to_datetime(df["created_date"].fillna(df["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None) >= prev_period_start) &
    (pd.to_datetime(df["created_date"].fillna(df["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None) < start_date)
]

# Key Metrics
st.markdown('<div class="section-header">Key Metrics</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    current_incidents = len(filtered)
    prev_incidents = len(prev_filtered)
    change = ((current_incidents - prev_incidents) / prev_incidents * 100) if prev_incidents > 0 else 0
    change_class = "metric-up" if change >= 0 else "metric-down"
    change_icon = "↑" if change >= 0 else "↓"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{current_incidents:,}</div>
        <div class="metric-label">Total Incidents</div>
        <div class="metric-change {change_class}">{change_icon} {abs(change):.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    locations = filtered["location_text"].nunique()
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{locations}</div>
        <div class="metric-label">Active Zones</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    avg_severity = filtered["severity"].mean() if not filtered.empty else 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{avg_severity:.2f}</div>
        <div class="metric-label">Avg Severity</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    critical = len(filtered[filtered["severity"] >= 4])
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{critical}</div>
        <div class="metric-label">Critical Cases</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    sources = filtered["source_name"].nunique()
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{sources}</div>
        <div class="metric-label">Data Sources</div>
    </div>
    """, unsafe_allow_html=True)

# Additional Insights
st.markdown('<div class="section-header"> Additional Insights</div>', unsafe_allow_html=True)
col6, col7, col8 = st.columns(3)

with col6:
    fatalities = filtered["fatalities"].sum() if "fatalities" in filtered else 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{fatalities:,}</div>
        <div class="metric-label">Total Fatalities</div>
    </div>
    """, unsafe_allow_html=True)

with col7:
    high_severity = len(filtered[filtered["severity"] >= 3])
    pct_high = (high_severity / len(filtered) * 100) if len(filtered) > 0 else 0
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{pct_high:.1f}%</div>
        <div class="metric-label">High Severity Rate</div>
    </div>
    """, unsafe_allow_html=True)

with col8:
    reporters = filtered["source_name"].nunique()
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{reporters}</div>
        <div class="metric-label">Unique Sources</div>
    </div>
    """, unsafe_allow_html=True)

# Download button
st.download_button(
    label= Download Filtered Data",
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
st.markdown('<div class="section-header"> Interactive Crisis Map</div>', unsafe_allow_html=True)

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

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #94a3b8; padding: 2rem 0;'>
    <p> Haiti Violence Analysis Dashboard | Data updated in real-time</p>
    <p> Main source: ReliefWeb</p>
    <p style='font-size: 0.85rem; margin-top: 0.5rem;'>Built with Streamlit & Plotly | © 2024</p>
</div>
""", unsafe_allow_html=True)
