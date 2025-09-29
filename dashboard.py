import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

DB_PATH = "reports.db"

st.set_page_config(
    page_title="Haiti Crisis Intelligence Center",
    page_icon="🇭🇹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern gradient theme with better contrast
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Main theme */
    .stApp {
        background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Enhanced header with animation */
    .main-header {
        background: linear-gradient(135deg, rgba(88, 166, 255, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%);
        border: 1px solid rgba(88, 166, 255, 0.3);
        border-radius: 20px;
        padding: 2.5rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
        animation: headerGlow 3s ease-in-out infinite;
    }
    
    @keyframes headerGlow {
        0%, 100% { box-shadow: 0 0 20px rgba(88, 166, 255, 0.3); }
        50% { box-shadow: 0 0 30px rgba(147, 51, 234, 0.4); }
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(88, 166, 255, 0.05) 0%, transparent 70%);
        animation: rotate 20s linear infinite;
    }
    
    @keyframes rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    .main-header h1 {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #58a6ff 0%, #9333ea 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        position: relative;
        z-index: 1;
    }
    
    .main-header .subtitle {
        color: #a8b2d1;
        font-size: 1.1rem;
        font-weight: 400;
        position: relative;
        z-index: 1;
    }
    
    /* Section headers with accent */
    .section-header {
        font-size: 0.9rem;
        font-weight: 700;
        background: linear-gradient(90deg, #58a6ff 0%, #9333ea 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 2.5rem 0 1.5rem 0;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .section-header::before {
        content: '';
        display: inline-block;
        width: 4px;
        height: 20px;
        background: linear-gradient(180deg, #58a6ff 0%, #9333ea 100%);
        border-radius: 2px;
    }
    
    /* Enhanced metric cards */
    .metric-card {
        background: rgba(30, 30, 46, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(88, 166, 255, 0.2);
        border-radius: 16px;
        padding: 1.8rem;
        position: relative;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #58a6ff 0%, #9333ea 100%);
        transform: scaleX(0);
        transition: transform 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        border-color: rgba(147, 51, 234, 0.4);
        box-shadow: 0 10px 40px rgba(88, 166, 255, 0.2);
    }
    
    .metric-card:hover::before {
        transform: scaleX(1);
    }
    
    .metric-value {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #58a6ff 0%, #9333ea 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #a8b2d1;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    
    .metric-change {
        font-size: 0.9rem;
        font-weight: 600;
        margin-top: 0.8rem;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 10px;
        border-radius: 20px;
    }
    
    .metric-up {
        color: #10b981;
        background: rgba(16, 185, 129, 0.1);
    }
    
    .metric-down {
        color: #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }
    
    /* Resource cards styling */
    .resource-card {
        background: linear-gradient(135deg, rgba(30, 30, 46, 0.8) 0%, rgba(30, 30, 46, 0.6) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(88, 166, 255, 0.2);
        border-radius: 16px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
    }
    
    .resource-card:hover {
        border-color: rgba(147, 51, 234, 0.3);
        box-shadow: 0 8px 30px rgba(88, 166, 255, 0.15);
        transform: translateX(5px);
    }
    
    .resource-card h3 {
        color: #58a6ff;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .resource-card h3::before {
        content: '▸';
        color: #9333ea;
        font-size: 1.2rem;
    }
    
    .org-item {
        background: rgba(88, 166, 255, 0.05);
        border-left: 3px solid transparent;
        border-image: linear-gradient(180deg, #58a6ff 0%, #9333ea 100%) 1;
        padding: 1rem;
        margin-bottom: 1.2rem;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .org-item:hover {
        background: rgba(88, 166, 255, 0.1);
        transform: translateX(5px);
    }
    
    .org-name {
        color: #f0f6fc;
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .org-detail {
        color: #a8b2d1;
        font-size: 0.9rem;
        margin: 0.2rem 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .org-detail a {
        color: #58a6ff;
        text-decoration: none;
        transition: color 0.3s ease;
    }
    
    .org-detail a:hover {
        color: #9333ea;
        text-decoration: underline;
    }
    
    /* Emergency hotline card */
    .emergency-card {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
        border: 2px solid rgba(239, 68, 68, 0.3);
        border-radius: 20px;
        padding: 2rem;
        margin: 2rem 0;
        position: relative;
        overflow: hidden;
    }
    
    .emergency-card::before {
        content: '⚠️';
        position: absolute;
        top: -20px;
        right: -20px;
        font-size: 80px;
        opacity: 0.1;
    }
    
    .emergency-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 1.5rem;
        margin-top: 1.5rem;
    }
    
    .emergency-item {
        text-align: center;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    
    .emergency-item:hover {
        background: rgba(255, 255, 255, 0.1);
        transform: scale(1.05);
    }
    
    .emergency-number {
        font-size: 2rem;
        font-weight: 800;
        color: #ef4444;
        margin: 0.5rem 0;
    }
    
    .emergency-label {
        color: #f0f6fc;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: rgba(30, 30, 46, 0.95);
        border-right: 1px solid rgba(88, 166, 255, 0.2);
    }
    
    /* Button styling */
    .stButton button {
        background: linear-gradient(135deg, #58a6ff 0%, #9333ea 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(88, 166, 255, 0.4);
    }
    
    /* Download button special */
    .stDownloadButton button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    }
    
    /* Selectbox and slider styling */
    .stSelectbox label, .stSlider label {
        color: #a8b2d1;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
    }
    
    /* Info boxes */
    .stAlert {
        background: rgba(88, 166, 255, 0.1);
        border: 1px solid rgba(88, 166, 255, 0.3);
        border-radius: 10px;
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
    st.error("⚠️ No data found. Please run harvester.py first to populate the database.")
    st.stop()

# Enhanced Header with animation
st.markdown("""
<div class="main-header">
    <h1>Haiti Crisis Intelligence Center</h1>
    <p class="subtitle">Real-time conflict monitoring • Predictive analytics • Humanitarian coordination</p>
</div>
""", unsafe_allow_html=True)

# Sidebar with better styling
with st.sidebar:
    st.markdown("### 🎯 Data Filters")
    
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

# Calculate trends
prev_period_start = start_date - (end_date - start_date)
prev_filtered = df[
    (pd.to_datetime(df["created_date"].fillna(df["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None) >= prev_period_start) &
    (pd.to_datetime(df["created_date"].fillna(df["timestamp"]), utc=True, errors="coerce").dt.tz_convert(None) < start_date)
]

# Key Metrics Section
st.markdown('<div class="section-header">Key Performance Indicators</div>', unsafe_allow_html=True)

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
        <div class="metric-label">Critical Events</div>
    </div>
    ''', unsafe_allow_html=True)

with col5:
    sources = filtered["source_name"].nunique()
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-value">{sources}</div>
        <div class="metric-label">Data Sources</div>
    </div>
    ''', unsafe_allow_html=True)

# Download button with better placement
col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    st.download_button(
        label="📥 Export Data (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"haiti_crisis_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# Analytics sections with enhanced visuals
st.markdown('<div class="section-header">Temporal Analysis</div>', unsafe_allow_html=True)

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
            line=dict(color='#58a6ff', width=3),
            marker=dict(size=10, color='#9333ea', line=dict(color='#58a6ff', width=2)),
            fill='tozeroy',
            fillcolor='rgba(88, 166, 255, 0.1)'
        ))
        
        fig_monthly.update_layout(
            title="Monthly Incident Trends",
            xaxis_title="Month",
            yaxis_title="Number of Incidents",
            template="plotly_dark",
            plot_bgcolor='rgba(30, 30, 46, 0.5)',
            paper_bgcolor='rgba(15, 15, 35, 0)',
            font=dict(color='#a8b2d1', family='Inter'),
            height=350,
            margin=dict(l=50, r=20, t=40, b=50),
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
                colorscale=[[0, '#58a6ff'], [1, '#9333ea']],
                showscale=False,
                line=dict(color='rgba(255,255,255,0.3)', width=1)
            )
        ))
        
        fig_weekly.update_layout(
            title="Weekly Pattern (Last 8 Weeks)",
            xaxis_title="Week Starting",
            yaxis_title="Number of Incidents",
            template="plotly_dark",
            plot_bgcolor='rgba(30, 30, 46, 0.5)',
            paper_bgcolor='rgba(15, 15, 35, 0)',
            font=dict(color='#a8b2d1', family='Inter'),
            height=350,
            margin=dict(l=50, r=20, t=40, b=50)
        )
        
        st.plotly_chart(fig_weekly, use_container_width=True)

# Humanitarian Resources Section - Properly formatted
st.markdown('<div class="section-header">Humanitarian Resources & Emergency Contacts</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    # UN & International Organizations
    st.markdown("""
    <div class="resource-card">
        <h3>UN & International Organizations</h3>
        
        <div class="org-item">
            <div class="org-name">OCHA Haiti (UN Coordination)</div>
            <div class="org-detail">📞 Emergency: +509 3701 0324</div>
            <div class="org-detail">✉️ ochHaiti@un.org</div>
            <div class="org-detail">🌐 <a href="https://www.unocha.org/haiti" target="_blank">unocha.org/haiti</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">UNICEF Haiti</div>
            <div class="org-detail">📞 +509 2812 3000</div>
            <div class="org-detail">✉️ portauprince@unicef.org</div>
            <div class="org-detail">🌐 <a href="https://www.unicef.org/haiti" target="_blank">unicef.org/haiti</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">World Food Programme (WFP)</div>
            <div class="org-detail">📞 +509 2940 5900</div>
            <div class="org-detail">✉️ wfp.haiti@wfp.org</div>
            <div class="org-detail">🌐 <a href="https://www.wfp.org/countries/haiti" target="_blank">wfp.org/countries/haiti</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">International Organization for Migration (IOM)</div>
            <div class="org-detail">📞 +509 2943 5201</div>
            <div class="org-detail">✉️ iomhaiti@iom.int</div>
            <div class="org-detail">🌐 <a href="https://haiti.iom.int" target="_blank">haiti.iom.int</a></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Medical Organizations
    st.markdown("""
    <div class="resource-card">
        <h3>Medical & Health Organizations</h3>
        
        <div class="org-item">
            <div class="org-name">Médecins Sans Frontières (MSF)</div>
            <div class="org-detail">📞 Emergency: +509 3458 0000</div>
            <div class="org-detail">✉️ msfocb-haiti-communication@brussels.msf.org</div>
            <div class="org-detail">🌐 <a href="https://www.msf.org/haiti" target="_blank">msf.org/haiti</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">Partners In Health (PIH)</div>
            <div class="org-detail">📞 +509 3701 5105</div>
            <div class="org-detail">✉️ info@pih.org</div>
            <div class="org-detail">🌐 <a href="https://www.pih.org/country/haiti" target="_blank">pih.org/country/haiti</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">International Medical Corps</div>
            <div class="org-detail">📞 +509 3702 7979</div>
            <div class="org-detail">✉️ haiti@internationalmedicalcorps.org</div>
            <div class="org-detail">🌐 <a href="https://internationalmedicalcorps.org/country/haiti" target="_blank">internationalmedicalcorps.org</a></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    # Protection & Child Welfare
    st.markdown("""
    <div class="resource-card">
        <h3>Protection & Child Welfare</h3>
        
        <div class="org-item">
            <div class="org-name">Save the Children Haiti</div>
            <div class="org-detail">📞 +509 2816 1758</div>
            <div class="org-detail">✉️ haiti@savethechildren.org</div>
            <div class="org-detail">🌐 <a href="https://www.savethechildren.org" target="_blank">savethechildren.org</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">CARE Haiti</div>
            <div class="org-detail">📞 +509 2813 9200</div>
            <div class="org-detail">✉️ info@care.org</div>
            <div class="org-detail">🌐 <a href="https://www.care.org" target="_blank">care.org</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">Plan International Haiti</div>
            <div class="org-detail">📞 +509 2813 2620</div>
            <div class="org-detail">✉️ haiti.co@plan-international.org</div>
            <div class="org-detail">🌐 <a href="https://plan-international.org/haiti" target="_blank">plan-international.org</a></div>
        </div>
        
        <div class="org-item">
            <div class="org-name">International Rescue Committee (IRC)</div>
            <div class="org-detail">📞 +509 2940 4242</div>
            <div class="org-detail">✉️ haiti@rescue.org</div>
            <div class="org-detail">🌐 <a href="https://www.rescue.org/country/haiti" target="_blank">rescue.org</a></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
