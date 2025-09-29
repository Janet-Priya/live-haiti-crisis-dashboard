import sqlite3
# Access columns by name
def get_db_connection():
    conn = sqlite3.connect('reports.db')
    conn.row_factory = sqlite3.Row  
    return conn

def create_reports_table():
    """
    Reports table with schema aligned to harvester.py (title + location_coords for compatibility).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            title TEXT,  -- report title
            raw_text TEXT NOT NULL,
            event_type TEXT,
            specific_type TEXT,
            broad_category TEXT,
            location_text TEXT,
            location_coords TEXT,  -- keep for compatibility
            latitude REAL,
            longitude REAL,
            location_metadata TEXT,
            displaced_people INTEGER,
            schools_closed INTEGER,
            children_recruited INTEGER,
            source_name TEXT,
            content_type TEXT,
            severity INTEGER,
            report_url TEXT,
            created_date TEXT
        );
    """)
    conn.commit()
    conn.close()

def migrate_reports_table():
    """
    Safely add new columns if they don't exist (for existing databases).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    new_columns = {
        "title": "TEXT",
        "location_coords": "TEXT",   # add back for compatibility
        "specific_type": "TEXT",
        "broad_category": "TEXT",
        "latitude": "REAL",
        "longitude": "REAL",
        "location_metadata": "TEXT",
        "displaced_people": "INTEGER",
        "schools_closed": "INTEGER",
        "children_recruited": "INTEGER",
        "source_name": "TEXT",
        "content_type": "TEXT",
        "severity": "INTEGER",
        "report_url": "TEXT",
        "created_date": "TEXT"
    }
    
    for col, col_type in new_columns.items():
        try:
            cursor.execute(f"ALTER TABLE reports ADD COLUMN {col} {col_type}")
            print(f"Added column {col}")
        except sqlite3.OperationalError:
            pass  # Column exists, ignore
    
    conn.commit()
    conn.close()

def create_location_hierarchy_table():
    """
    Store Haiti's location hierarchy with lat/lon split.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_hierarchy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT UNIQUE NOT NULL,
            location_type TEXT NOT NULL,
            parent_location TEXT,
            department TEXT,
            latitude REAL,
            longitude REAL,
            risk_level TEXT,
            population_estimate INTEGER,
            notes TEXT
        );
    """)
    
    locations_data = [
        ("Cité Soleil", "slum", "Port-au-Prince", "Ouest", 18.5944, -72.3251, "critical", 400000, "Largest slum, high gang activity"),
        ("Martissant", "neighborhood", "Port-au-Prince", "Ouest", 18.5089, -72.3570, "critical", 150000, "Gang-controlled area"),
        ("Bel Air", "neighborhood", "Port-au-Prince", "Ouest", 18.5463, -72.3387, "high", 100000, "Dense urban area"),
        ("Delmas", "neighborhood", "Port-au-Prince", "Ouest", 18.5456, -72.3084, "medium", 200000, "Mixed residential/commercial"),
        ("Pétion-Ville", "neighborhood", "Port-au-Prince", "Ouest", 18.5125, -72.2851, "low", 80000, "Wealthy suburb"),
        ("La Saline", "slum", "Port-au-Prince", "Ouest", 18.5539, -72.3478, "critical", 50000, "Port area slum"),
        ("Village de Dieu", "slum", "Port-au-Prince", "Ouest", 18.5200, -72.3600, "critical", 30000, "Informal settlement"),
        ("Carrefour", "commune", "Port-au-Prince", "Ouest", 18.5417, -72.3958, "high", 500000, "Large commune"),
        ("Tabarre", "commune", "Port-au-Prince", "Ouest", 18.5833, -72.2833, "medium", 100000, "Residential area"),
        ("Croix-des-Bouquets", "commune", "Port-au-Prince Metro", "Ouest", 18.5833, -72.2167, "high", 200000, "Agricultural commune"),
        ("Léogâne", "commune", "Port-au-Prince Metro", "Ouest", 18.5167, -72.6333, "medium", 200000, "Coastal town"),
        ("Gonaïves", "city", "Gonaïves", "Artibonite", 19.4500, -72.6900, "high", 300000, "Major port city"),
        ("Saint-Marc", "city", "Saint-Marc", "Artibonite", 19.1167, -72.7000, "medium", 250000, "Industrial city"),
        ("Cap-Haïtien", "city", "Cap-Haïtien", "Nord", 19.7667, -72.2000, "medium", 274000, "Second largest city"),
        ("Les Cayes", "city", "Les Cayes", "Sud", 18.2000, -73.7500, "medium", 200000, "Southern port city"),
        ("Jacmel", "city", "Jacmel", "Sud-Est", 18.2333, -72.5333, "low", 140000, "Tourism center"),
        ("Jérémie", "city", "Jérémie", "Grande-Anse", 18.6500, -74.1167, "medium", 120000, "Western city"),
        ("Hinche", "city", "Hinche", "Centre", 19.1500, -71.9833, "medium", 100000, "Central plateau"),
    ]
    
    for location in locations_data:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO location_hierarchy 
                (location_name, location_type, parent_location, department, latitude, longitude, risk_level, population_estimate, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, location)
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()

def get_location_hierarchy():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT location_name, location_type, parent_location, department, 
               latitude, longitude, risk_level, population_estimate, notes
        FROM location_hierarchy 
        ORDER BY 
            CASE location_type 
                WHEN 'slum' THEN 1
                WHEN 'neighborhood' THEN 2 
                WHEN 'commune' THEN 3
                WHEN 'city' THEN 4
                ELSE 5 
            END,
            location_name
    """)
    locations = cursor.fetchall()
    conn.close()
    return [dict(row) for row in locations]

def get_reports_by_precise_location():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            r.location_text,
            r.event_type,
            r.broad_category,
            COUNT(*) as report_count,
            r.latitude,
            r.longitude,
            r.location_metadata,
            MAX(r.timestamp) as latest_report,
            lh.risk_level,
            lh.location_type,
            lh.department,
            SUM(COALESCE(r.displaced_people,0)) as total_displaced,
            SUM(COALESCE(r.schools_closed,0)) as total_schools_closed,
            SUM(COALESCE(r.children_recruited,0)) as total_children_recruited
        FROM reports r
        LEFT JOIN location_hierarchy lh ON r.location_text = lh.location_name
        WHERE r.location_text IS NOT NULL AND r.location_text != ''
        GROUP BY r.location_text, r.event_type, r.broad_category
        ORDER BY report_count DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return [dict(row) for row in results]

def create_dashboard_views():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS location_analytics AS
        SELECT 
            r.location_text,
            r.broad_category,
            lh.location_type,
            lh.department,
            lh.risk_level,
            COUNT(*) as total_reports,
            COUNT(CASE WHEN r.event_type = 'violence' THEN 1 END) as violence_reports,
            COUNT(CASE WHEN r.event_type = 'school_closure' THEN 1 END) as school_closures,
            COUNT(CASE WHEN r.event_type = 'displacement' THEN 1 END) as displacement_reports,
            COUNT(CASE WHEN r.event_type = 'aid_needed' THEN 1 END) as aid_requests,
            SUM(COALESCE(r.displaced_people,0)) as total_displaced,
            SUM(COALESCE(r.schools_closed,0)) as total_schools_closed,
            SUM(COALESCE(r.children_recruited,0)) as total_children_recruited,
            MAX(r.timestamp) as latest_incident,
            r.latitude,
            r.longitude
        FROM reports r
        LEFT JOIN location_hierarchy lh ON r.location_text = lh.location_name
        WHERE r.location_text IS NOT NULL AND r.location_text != ''
        GROUP BY r.location_text, r.broad_category, lh.location_type, lh.department, lh.risk_level, r.latitude, r.longitude
    """)
    
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS time_analytics AS
        SELECT 
            DATE(timestamp) as report_date,
            event_type,
            broad_category,
            location_text,
            COUNT(*) as daily_count,
            SUM(COALESCE(displaced_people,0)) as total_displaced,
            SUM(COALESCE(schools_closed,0)) as total_schools_closed,
            SUM(COALESCE(children_recruited,0)) as total_children_recruited
        FROM reports
        WHERE location_text IS NOT NULL AND location_text != ''
        GROUP BY DATE(timestamp), event_type, broad_category, location_text
        ORDER BY report_date DESC
    """)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    print("Creating enhanced database structure...")
    create_reports_table()
    migrate_reports_table()
    create_location_hierarchy_table()
    create_dashboard_views()
    print("Enhanced database structure created successfully with full schema.")

    print("\nHaiti Location Hierarchy (Top 10):")
    locations = get_location_hierarchy()
    for loc in locations[:10]:
        print(f"  {loc['location_name']} ({loc['location_type']}) - Risk: {loc['risk_level']}")
