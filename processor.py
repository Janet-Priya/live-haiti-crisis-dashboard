import os
import json
import sqlite3
import time
from datetime import datetime
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from database import get_db_connection

# Load environment variables
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Haiti-specific location knowledge base
HAITI_LOCATIONS = {
    "cite_soleil": {"names": ["Cité Soleil", "Cite Soleil", "Soleil"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "martissant": {"names": ["Martissant"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "bel_air": {"names": ["Bel Air", "Belair"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "delmas": {"names": ["Delmas"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "petion_ville": {"names": ["Pétion-Ville", "Petion-Ville", "Petionville"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "carrefour": {"names": ["Carrefour"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "tabarre": {"names": ["Tabarre"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "croix_des_bouquets": {"names": ["Croix-des-Bouquets", "Croix des Bouquets"], "type": "commune", "parent": "Ouest"},
    "kenscoff": {"names": ["Kenscoff", "Kenskoff"], "type": "commune", "parent": "Ouest"},
    "gressier": {"names": ["Gressier"], "type": "commune", "parent": "Ouest"},
    "grand_goave": {"names": ["Grand-Goâve", "Grand Goave"], "type": "commune", "parent": "Ouest"},
    "leogane": {"names": ["Léogâne", "Leogane"], "type": "commune", "parent": "Ouest"},
    "gonaives": {"names": ["Gonaïves", "Gonaives"], "type": "city", "parent": "Artibonite"},
    "saint_marc": {"names": ["Saint-Marc", "Saint Marc"], "type": "city", "parent": "Artibonite"},
    "dessalines": {"names": ["Dessalines"], "type": "commune", "parent": "Artibonite"},
    "ponte_sonde": {"names": ["Ponte-Sondé", "Ponte Sonde"], "type": "commune", "parent": "Artibonite"},
    "cap_haitien": {"names": ["Cap-Haïtien", "Cap-Haitien", "Cap Haitien", "Le Cap"], "type": "city", "parent": "Nord"},
    "fort_dauphin": {"names": ["Fort-Dauphin", "Fort Dauphin"], "type": "commune", "parent": "Nord"},
    "ouanaminthe": {"names": ["Ouanaminthe"], "type": "commune", "parent": "Nord"},
    "fort_liberte": {"names": ["Fort-Liberté", "Fort Liberte"], "type": "commune", "parent": "Nord-Est"},
    "les_cayes": {"names": ["Les Cayes", "Cayes"], "type": "city", "parent": "Sud"},
    "jeremie": {"names": ["Jérémie", "Jeremie"], "type": "city", "parent": "Grande-Anse"},
    "hinche": {"names": ["Hinche"], "type": "city", "parent": "Centre"},
    "mirebalais": {"names": ["Mirebalais"], "type": "commune", "parent": "Centre"},
    "miragoane": {"names": ["Miragoâne", "Miragoane"], "type": "city", "parent": "Nippes"},
    "jacmel": {"names": ["Jacmel"], "type": "city", "parent": "Sud-Est"},
    "la_saline": {"names": ["La Saline", "Lasaline"], "type": "slum", "parent": "Port-au-Prince"},
    "boston": {"names": ["Boston"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "village_de_dieu": {"names": ["Village de Dieu"], "type": "slum", "parent": "Port-au-Prince"},
    "tokyo": {"names": ["Tokyo"], "type": "neighborhood", "parent": "Port-au-Prince"},
    "wharf_jeremie": {"names": ["Wharf Jérémie", "Wharf Jeremie"], "type": "neighborhood", "parent": "Port-au-Prince"},
}

def find_specific_haiti_location(text):
    text_lower = text.lower()
    found_locations = []
    for key, data in HAITI_LOCATIONS.items():
        for name_variant in data["names"]:
            if name_variant.lower() in text_lower:
                found_locations.append({
                    'name': name_variant,
                    'type': data['type'],
                    'parent': data['parent'],
                    'key': key
                })
    if found_locations:
        priority_order = {'slum': 4, 'neighborhood': 3, 'commune': 2, 'city': 1}
        found_locations.sort(key=lambda x: priority_order.get(x['type'], 0), reverse=True)
        return found_locations[0]
    return None

def process_with_gemini_coordinates(raw_text, retries=3, delay=5):
    prompt = f"""
    You are analyzing a humanitarian report about Haiti. Extract key information.

    EVENT TYPES:
    - school_closure
    - school_destruction
    - child_recruitment
    - displacement
    - aid_needed
    - violence
    - health_crisis
    - food_insecurity

    LOCATION: Extract the MOST SPECIFIC Haiti location. Return latitude and longitude in decimal degrees.
    Prioritize neighborhoods/slums > communes > cities > departments.

    Return ONLY JSON: {{"event_type": "...", "location": "...", "latitude": ..., "longitude": ...}}

    TEXT:
    "{raw_text}"
    """
    safety_settings = [
        {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
    ]
    for i in range(retries):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt, safety_settings=safety_settings)
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            print(f"Gemini attempt {i+1} failed: {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                return {"event_type": "other", "location": "", "latitude": None, "longitude": None}

def process_and_store_report_with_coords(raw_text, created_date: str | None = None):
    print(f"Processing: {raw_text[:80]}...")
    local_location = find_specific_haiti_location(raw_text)
    ai_result = process_with_gemini_coordinates(raw_text)
    
    # ✅ Convert event_type to string if it's a list
    event_type = ai_result.get("event_type", "other")
    if isinstance(event_type, list):
        event_type = ", ".join(event_type)
    elif not isinstance(event_type, str):
        event_type = str(event_type)
    
    ai_location = ai_result.get("location", "")
    lat = ai_result.get("latitude")
    lon = ai_result.get("longitude")
    
    # Decide final location based on AI and local knowledge
    final_location = ai_location
    if local_location and (not ai_location or len(local_location['name']) > len(ai_location)):
        final_location = local_location['name']
    
    # Ensure lat/lon are numbers or None
    if not isinstance(lat, (int, float)):
        lat = None
    if not isinstance(lon, (int, float)):
        lon = None
    
    # Build location metadata
    if local_location:
        location_metadata = json.dumps({
            "type": local_location["type"],
            "parent": local_location["parent"],
            "precision": "high"
        })
    elif final_location:
        location_metadata = json.dumps({"precision": "medium"})
    else:
        location_metadata = json.dumps({"precision": "low"})
    
    # Store in DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reports (
            timestamp, raw_text, event_type, location_text,
            latitude, longitude, location_metadata, created_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        raw_text,
        event_type,
        final_location,
        lat,
        lon,
        location_metadata,
        created_date
    ))
    conn.commit()
    conn.close()
    
    print(f"Stored: {event_type} @ {final_location} ({lat}, {lon})")
    return True

def get_location_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT location_text, location_metadata, COUNT(*) 
        FROM reports 
        WHERE location_text IS NOT NULL AND location_text != '' 
        GROUP BY location_text 
        ORDER BY COUNT(*) DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    print("=== Location Stats ===")
    for loc, metadata, count in rows:
        try:
            meta = json.loads(metadata)
            precision = meta.get("precision", "unknown")
        except:
            precision = "unknown"
        print(f"  {loc}: {count} reports [{precision}]")

if __name__ == "__main__":
    get_location_statistics()
