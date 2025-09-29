import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

DB_PATH = "reports.db"

st.set_page_config(
    page_title="Haiti Violence Analysis Dashboard",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced dark styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    body, .stApp { 
        background: #0d1117 !important; 
        color: #e6edf3; 
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
    }
    
    .main-header {
        background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    
    .main-header h1 { 
        font-size: 2rem; 
        font-weight: 700; 
        margin-bottom: 0.5rem; 
        color: #f0f6fc;
        letter-spacing: -0.5px;
    }
    
    .main-header p { 
        color: #8b949e; 
        margin: 0;
        font-size: 0.95rem;
    }
    
    .section-header { 
        font-size: 1rem; 
        font-weight: 600; 
        color: #f0f6fc; 
        margin: 2rem 0 1rem 0; 
        padding-bottom: 0.5rem; 
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    
    .metric-card { 
        background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
        border: 1px solid #30363d; 
        border-radius: 12px; 
        padding: 1.5rem; 
        margin: 0.5rem 0; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #58a6ff;
        font-family: 'SF Mono', 'Monaco', monospace;
        margin-bottom: 0.25rem;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
    }
    
    .metric-change {
        font-size: 0.85rem;
        margin-top: 0.5rem;
    }
    
    .metric-up { color: #3fb950; }
    .metric-down { color: #f85149; }
    
    .stDownloadButton button { 
        background: #21262d; 
        border: 1px solid #30363d; 
        color: #e6edf3;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stDownloadButton button:hover {
        background: #30363d;
        border-color: #58a6ff;
    }
    
    div[data-testid="stSidebarNav"] {
        background: #0d1117;
    }
    
    .css-1d391kg {
        background: #161b22;
    }
</style>
""", unsafe_allow_html=True)

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
    <h1>Haiti Violence Analysis Dashboard</h1>
    <p>Real-time conflict monitoring and predictive intelligence</p>
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
    change_class = "metric-up" if change > 0 else "metric-down"
    change_icon = "↑" if change > 0 else "↓"
    
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-value">{current_incidents:,}</div>
        <div class="metric-label">Total Incidents</div>
        <div class="metric-change {change_class}">{change_icon} {abs(change):.1f}%</div>
    </div>
    ''', unsafe_allow_html=True)

with col2:
    locations = filtered["location_text"].nunique()
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-value">{locations}</div>
        <div class="metric-label">Active Zones</div>
    </div>
    ''', unsafe_allow_html=True)

with col3:
    avg_severity = filtered["severity"].mean() if not filtered.empty else 0
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-value">{avg_severity:.2f}</div>
        <div class="metric-label">Avg Severity</div>
    </div>
    ''', unsafe_allow_html=True)

with col4:
    critical = len(filtered[filtered["severity"] >= 4])
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-value">{critical}</div>
        <div class="metric-label">Critical</div>
    </div>
    ''', unsafe_allow_html=True)

with col5:
    sources = filtered["source_name"].nunique()
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-value">{sources}</div>
        <div class="metric-label">Sources</div>
    </div>
    ''', unsafe_allow_html=True)

# Download button
st.download_button(
    label="Download Filtered Data",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name=f"haiti_crisis_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

# Incident Trends Over Time
st.markdown('<div class="section-header">Incident Trends Over Time</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    # Monthly trend
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
            line=dict(color='#58a6ff', width=3),
            marker=dict(size=8, color='#58a6ff'),
            fill='tozeroy',
            fillcolor='rgba(88, 166, 255, 0.1)'
        ))
        
        fig_monthly.update_layout(
            title="Monthly Incident Trends",
            xaxis_title="Month",
            yaxis_title="Incidents",
            template="plotly_dark",
            plot_bgcolor='#0d1117',
            paper_bgcolor='#0d1117',
            font=dict(color='#e6edf3', family='Inter'),
            height=300,
            margin=dict(l=50, r=20, t=40, b=50)
        )
        
        st.plotly_chart(fig_monthly, use_container_width=True)

with col2:
    # Weekly trend
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
                colorscale='Reds',
                showscale=False
            )
        ))
        
        fig_weekly.update_layout(
            title="Weekly Incident Pattern (Last 8 Weeks)",
            xaxis_title="Week",
            yaxis_title="Incidents",
            template="plotly_dark",
            plot_bgcolor='#0d1117',
            paper_bgcolor='#0d1117',
            font=dict(color='#e6edf3', family='Inter'),
            height=300,
            margin=dict(l=50, r=20, t=40, b=50)
        ))
        
        st.plotly_chart(fig_weekly, use_container_width=True)

# Analysis grids
col1, col2 = st.columns(2)

with col1:
    # Top violence hotspots
    st.markdown('<div class="section-header">Top Violence Hotspots</div>', unsafe_allow_html=True)
    
    location_counts = filtered['location_text'].value_counts().head(5).reset_index()
    location_counts.columns = ['Location', 'Incidents']
    
    fig_hotspots = go.Figure()
    fig_hotspots.add_trace(go.Bar(
        x=location_counts['Incidents'],
        y=location_counts['Location'],
        orientation='h',
        marker=dict(
            color=location_counts['Incidents'],
            colorscale='Reds',
            showscale=False
        ),
        text=location_counts['Incidents'],
        textposition='outside'
    ))
    
    fig_hotspots.update_layout(
        template="plotly_dark",
        plot_bgcolor='#0d1117',
        paper_bgcolor='#0d1117',
        font=dict(color='#e6edf3', family='Inter'),
        height=300,
        margin=dict(l=150, r=20, t=20, b=50),
        xaxis_title="Number of Incidents",
        yaxis_title=""
    )
    
    st.plotly_chart(fig_hotspots, use_container_width=True)
    
    # Daily incident heatmap
    st.markdown('<div class="section-header">Daily Incident Heatmap</div>', unsafe_allow_html=True)
    
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
        
        # Reorder days
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_pivot = heatmap_pivot.reindex([d for d in day_order if d in heatmap_pivot.index])
        
        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=heatmap_pivot.columns,
            y=heatmap_pivot.index,
            colorscale='Reds',
            showscale=True
        ))
        
        fig_heatmap.update_layout(
            template="plotly_dark",
            plot_bgcolor='#0d1117',
            paper_bgcolor='#0d1117',
            font=dict(color='#e6edf3', family='Inter'),
            height=300,
            margin=dict(l=100, r=20, t=20, b=50),
            xaxis_title="Hour of Day",
            yaxis_title=""
        )
        
        st.plotly_chart(fig_heatmap, use_container_width=True)

with col2:
    # Incident severity distribution
    st.markdown('<div class="section-header">Incident Severity Distribution</div>', unsafe_allow_html=True)
    
    severity_counts = filtered['severity'].value_counts().sort_index().reset_index()
    severity_counts.columns = ['Severity', 'Count']
    severity_counts['Severity'] = severity_counts['Severity'].astype(str)
    
    fig_severity = go.Figure()
    fig_severity.add_trace(go.Pie(
        labels=severity_counts['Severity'],
        values=severity_counts['Count'],
        hole=0.5,
        marker=dict(colors=['#3fb950', '#58a6ff', '#f0883e', '#f85149', '#d73a49'])
    ))
    
    fig_severity.update_layout(
        template="plotly_dark",
        plot_bgcolor='#0d1117',
        paper_bgcolor='#0d1117',
        font=dict(color='#e6edf3', family='Inter'),
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True
    )
    
    st.plotly_chart(fig_severity, use_container_width=True)
    
    # Monthly growth index
    st.markdown('<div class="section-header">Monthly Growth Index</div>', unsafe_allow_html=True)
    
    if 'created_date' in filtered.columns:
        monthly_growth = filtered.groupby("month").size().reset_index(name="count")
        monthly_growth['growth'] = monthly_growth['count'].pct_change() * 100
        
        fig_growth = go.Figure()
        fig_growth.add_trace(go.Bar(
            x=monthly_growth["month"],
            y=monthly_growth["growth"],
            marker=dict(
                color=monthly_growth["growth"],
                colorscale='RdYlGn_r',
                showscale=False
            )
        ))
        
        fig_growth.update_layout(
            title="Month-over-Month Change (%)",
            template="plotly_dark",
            plot_bgcolor='#0d1117',
            paper_bgcolor='#0d1117',
            font=dict(color='#e6edf3', family='Inter'),
            height=300,
            margin=dict(l=50, r=20, t=40, b=50),
            xaxis_title="Month",
            yaxis_title="Growth %"
        )
        
        st.plotly_chart(fig_growth, use_container_width=True)

# Predictive Intelligence
st.markdown('<div class="section-header">AI-Powered Incident Forecasting</div>', unsafe_allow_html=True)

if len(filtered) > 30:
    # Simple trend line for prediction
    filtered['days_since_start'] = (
        pd.to_datetime(filtered["created_date"].fillna(filtered["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None) - 
        pd.to_datetime(filtered["created_date"].fillna(filtered["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None).min()
    ).dt.days
    
    daily_counts = filtered.groupby('days_since_start').size().reset_index(name='count')
    
    # Simple moving average for prediction
    daily_counts['ma_7'] = daily_counts['count'].rolling(window=7, min_periods=1).mean()
    
    # Extend prediction
    last_day = daily_counts['days_since_start'].max()
    future_days = pd.DataFrame({'days_since_start': range(last_day + 1, last_day + 31)})
    future_days['ma_7'] = daily_counts['ma_7'].iloc[-1]  # Simple extension
    
    fig_forecast = go.Figure()
    
    # Historical data
    fig_forecast.add_trace(go.Scatter(
        x=daily_counts['days_since_start'],
        y=daily_counts['count'],
        mode='lines',
        name='Actual',
        line=dict(color='#58a6ff', width=2)
    ))
    
    # Moving average
    fig_forecast.add_trace(go.Scatter(
        x=daily_counts['days_since_start'],
        y=daily_counts['ma_7'],
        mode='lines',
        name='7-day MA',
        line=dict(color='#f0883e', width=2, dash='dash')
    ))
    
    # Forecast
    fig_forecast.add_trace(go.Scatter(
        x=future_days['days_since_start'],
        y=future_days['ma_7'],
        mode='lines',
        name='Forecast',
        line=dict(color='#f85149', width=2, dash='dot'),
        fill='tonexty',
        fillcolor='rgba(248, 81, 73, 0.1)'
    ))
    
    fig_forecast.update_layout(
        title="30-Day Incident Forecast",
        xaxis_title="Days from Start",
        yaxis_title="Daily Incidents",
        template="plotly_dark",
        plot_bgcolor='#0d1117',
        paper_bgcolor='#0d1117',
        font=dict(color='#e6edf3', family='Inter'),
        height=400,
        margin=dict(l=50, r=20, t=40, b=50)
    )
    
    st.plotly_chart(fig_forecast, use_container_width=True)

# Interactive Map
st.markdown('<div class="section-header">Crisis Map</div>', unsafe_allow_html=True)

map_mode = st.radio("Map Visualization", ["Bubble Map", "Density Heatmap"], horizontal=True)

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
                    hover_data=["title", "source_name", "event_type"],
                    zoom=6.5,
                    height=650,
                    color_continuous_scale="Reds",
                    range_color=[1, 5]
                )
                
                fig_map.update_layout(
                    mapbox_style="carto-darkmatter",
                    template="plotly_dark",
                    margin=dict(l=0, r=0, t=0, b=0)
                )
                
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                fig_heat = px.density_mapbox(
                    geo_data,
                    lat="latitude",
                    lon="longitude",
                    z="severity",
                    radius=18,
                    zoom=6.5,
                    height=650,
                    mapbox_style="carto-darkmatter",
                    color_continuous_scale="Reds"
                )
                
                fig_heat.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0)
                )
                
                st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("No geocoded incidents available for mapping.")

# Humanitarian Resources Section
st.markdown('<div class="section-header">Humanitarian Resources & Emergency Contacts</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="metric-card">
        <h3 style="color: #58a6ff; margin-bottom: 1rem;">UN & International Organizations</h3>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">OCHA Haiti (UN Coordination)</strong><br>
            <span style="color: #8b949e;">Emergency: +509 3701 0324</span><br>
            <span style="color: #8b949e;">Email: ochHaiti@un.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.unocha.org/haiti" target="_blank" style="color: #58a6ff;">unocha.org/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">UNICEF Haiti</strong><br>
            <span style="color: #8b949e;">Phone: +509 2812 3000</span><br>
            <span style="color: #8b949e;">Email: portauprince@unicef.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.unicef.org/haiti" target="_blank" style="color: #58a6ff;">unicef.org/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">World Food Programme (WFP)</strong><br>
            <span style="color: #8b949e;">Phone: +509 2940 5900</span><br>
            <span style="color: #8b949e;">Email: wfp.haiti@wfp.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.wfp.org/countries/haiti" target="_blank" style="color: #58a6ff;">wfp.org/countries/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">International Organization for Migration (IOM)</strong><br>
            <span style="color: #8b949e;">Phone: +509 2943 5201</span><br>
            <span style="color: #8b949e;">Email: iomhaiti@iom.int</span><br>
            <span style="color: #8b949e;">Website: <a href="https://haiti.iom.int" target="_blank" style="color: #58a6ff;">haiti.iom.int</a></span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="metric-card" style="margin-top: 1rem;">
        <h3 style="color: #58a6ff; margin-bottom: 1rem;">Medical & Health Organizations</h3>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">Médecins Sans Frontières (MSF)</strong><br>
            <span style="color: #8b949e;">Emergency: +509 3458 0000</span><br>
            <span style="color: #8b949e;">Email: msfocb-haiti-communication@brussels.msf.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.msf.org/haiti" target="_blank" style="color: #58a6ff;">msf.org/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">Partners In Health (PIH)</strong><br>
            <span style="color: #8b949e;">Phone: +509 3701 5105</span><br>
            <span style="color: #8b949e;">Email: info@pih.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.pih.org/country/haiti" target="_blank" style="color: #58a6ff;">pih.org/country/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">International Medical Corps</strong><br>
            <span style="color: #8b949e;">Phone: +509 3702 7979</span><br>
            <span style="color: #8b949e;">Email: haiti@internationalmedicalcorps.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://internationalmedicalcorps.org/country/haiti" target="_blank" style="color: #58a6ff;">internationalmedicalcorps.org</a></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <h3 style="color: #58a6ff; margin-bottom: 1rem;">Protection & Child Welfare</h3>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">Save the Children Haiti</strong><br>
            <span style="color: #8b949e;">Phone: +509 2816 1758</span><br>
            <span style="color: #8b949e;">Email: haiti@savethechildren.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.savethechildren.org/haiti" target="_blank" style="color: #58a6ff;">savethechildren.org/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">CARE Haiti</strong><br>
            <span style="color: #8b949e;">Phone: +509 2813 9200</span><br>
            <span style="color: #8b949e;">Email: info@care.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.care.org/haiti" target="_blank" style="color: #58a6ff;">care.org/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">Plan International Haiti</strong><br>
            <span style="color: #8b949e;">Phone: +509 2813 2620</span><br>
            <span style="color: #8b949e;">Email: haiti.co@plan-international.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://plan-international.org/haiti" target="_blank" style="color: #58a6ff;">plan-international.org/haiti</a></span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">International Rescue Committee (IRC)</strong><br>
            <span style="color: #8b949e;">Phone: +509 2940 4242</span><br>
            <span style="color: #8b949e;">Email: haiti@rescue.org</span><br>
            <span style="color: #8b949e;">Website: <a href="https://www.rescue.org/country/haiti" target="_blank" style="color: #58a6ff;">rescue.org/country/haiti</a></span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="metric-card" style="margin-top: 1rem;">
        <h3 style="color: #58a6ff; margin-bottom: 1rem;">Local Haitian Organizations</h3>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">FONHDILAC (Human Rights Network)</strong><br>
            <span style="color: #8b949e;">Phone: +509 3701 2345</span><br>
            <span style="color: #8b949e;">Email: fonhdilac@gmail.com</span><br>
            <span style="color: #8b949e;">Focus: Human rights monitoring and protection</span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">RNDDH (National Network for Defense of Human Rights)</strong><br>
            <span style="color: #8b949e;">Phone: +509 2245 4288</span><br>
            <span style="color: #8b949e;">Email: rnddh@yahoo.fr</span><br>
            <span style="color: #8b949e;">Focus: Documentation and advocacy</span>
        </div>
        
        <div style="margin-bottom: 1rem;">
            <strong style="color: #f0f6fc;">Haitian Red Cross</strong><br>
            <span style="color: #8b949e;">Emergency: 118 (within Haiti)</span><br>
            <span style="color: #8b949e;">Phone: +509 2222 5654</span><br>
            <span style="color: #8b949e;">Focus: Emergency response and disaster relief</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="metric-card" style="margin-top: 1rem;">
    <h3 style="color: #58a6ff; margin-bottom: 1rem;">Emergency Hotlines</h3>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
        <div>
            <strong style="color: #f85149;">Police Emergency</strong><br>
            <span style="color: #8b949e; font-size: 1.2rem;">114</span>
        </div>
        <div>
            <strong style="color: #f85149;">Medical Emergency</strong><br>
            <span style="color: #8b949e; font-size: 1.2rem;">118</span>
        </div>
        <div>
            <strong style="color: #f85149;">Fire Department</strong><br>
            <span style="color: #8b949e; font-size: 1.2rem;">115</span>
        </div>
    </div>
    <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #30363d;">
        <strong style="color: #f0f6fc;">US Embassy Port-au-Prince (for US citizens)</strong><br>
        <span style="color: #8b949e;">Emergency: +509 2229 8000</span><br>
        <span style="color: #8b949e;">After hours: +1-202-501-4444</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; padding: 1rem; color: #8b949e; font-size: 0.85rem; margin-top: 2rem;">
    <strong>Note:</strong> Contact information verified as of 2024. Always verify current contact details before reaching out.<br>
    For real-time coordination, visit <a href="https://reliefweb.int/country/hti" target="_blank" style="color: #58a6ff;">ReliefWeb Haiti</a> for the latest humanitarian updates.
</div>
""", unsafe_allow_html=True)
