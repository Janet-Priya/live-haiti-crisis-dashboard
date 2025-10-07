# 🇭🇹 Haiti Crisis Data Dashboard  

## A Real-Time View into Haiti’s Humanitarian Emergency  

The **Haiti Crisis Data Dashboard** is a live, data-driven visualization tool that tracks and analyzes the ongoing humanitarian crisis in Haiti.  
By combining open-source event data, geospatial insights, and AI-assisted analytics, this platform sheds light on patterns of violence, displacement, and instability — transforming raw data into clarity and awareness.

---

## Purpose  

Haiti continues to face compounding crises — from political instability and gang-related violence to economic disruption and displacement.  
This dashboard aims to monitor, visualize, and communicate key crisis indicators, enabling researchers, journalists, and humanitarian organizations to:  

- Track reported incidents and conflict trends in near real-time  
- Identify hotspots and emerging risks across regions  
- Understand severity patterns and humanitarian impact  
- Support data-informed decision-making and rapid response  

---

## Features  

- Dynamic filtering to explore incidents by type, date, severity, and location  
- Live metrics showing totals, averages, and trends updated daily  
- Interactive maps for visualizing conflict and displacement patterns  
- Multi-language support (English, French, Haitian Creole)  
- Automated data harvesting via GitHub Actions and Google API  

---

## Data Sources  

- Verified open-source reports from humanitarian and media feeds  
- Aggregated datasets compiled through automated scripts (`harvester.py`)  
- Geocoding and mapping powered by Google Geolocation API and Geopy  
- Data processed with Pandas, NumPy, and visualized using Plotly  

> All data used is publicly available and intended solely for humanitarian research and awareness purposes.

---

## Automated Data Updates  

This project includes a GitHub Actions workflow (`.github/workflows/harvest.yml`) that automatically:  
- Runs the harvester script every 24 hours  
- Updates the local database (`reports.db`)  
- Commits and pushes the latest dataset to the repository  

**Current Schedule:**  
`0 0 * * *` → Every day at 00:00 UTC  

---

## Tech Stack  

| Component | Description |
|------------|-------------|
| Frontend | Streamlit (for live dashboards and UI) |
| Backend | Python 3.11 |
| Data Processing | Pandas, NumPy |
| Visualization | Plotly, Streamlit native charts |
| Automation | GitHub Actions |
| APIs | Google Generative AI, Geopy, Requests |

---

## Deployment  

The dashboard is hosted on **Streamlit Cloud** for continuous updates and public accessibility.  

To run locally:
```bash
pip install -r requirements.txt
streamlit run app.py

---

---

## Live Dashboard

**Visit the live version here:**  
[https://haiti-dashboard.streamlit.app](https://livehaiticrisisdashboard-eqz6uawzbzbpazrpn6n3zf.streamlit.app/#haiti-violence-analysis-dashboard)  
*(Replace this with your actual Streamlit app link.)*

---

## Harvester Workflow

The **harvester script** collects and stores structured event data into `reports.db`.  
It runs autonomously with minimal maintenance, logging key updates and changes in the dataset over time.

---

## Future Plans

- Integrate satellite or mobility data for humanitarian access mapping  
- Expand Haitian Creole translations across the interface  
- Add predictive analytics for early-warning indicators  
- Publish open dataset API for researchers and NGOs  

---

## Acknowledgements

This project is dedicated to the **resilience and strength of the Haitian people**,  
and to the global community striving for **transparency and humanitarian action** through open data.  

Developed and maintained by **Janet**
---



