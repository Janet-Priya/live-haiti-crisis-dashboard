import os
import json
import sqlite3
import time
from datetime import datetime
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
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
    "port_au_prince": {"names": ["Port-au-Prince", "Port au Prince"], "type": "city", "parent": "Ouest"}
}

def find_specific_haiti_location(text):
    """Find specific Haiti locations in text using knowledge base"""
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

def process_with_gemini_pro(raw_text, retries=3, delay=5):
    """Process text with Gemini Pro - fixed version"""
    prompt = f"""
    Analyze this Haiti humanitarian report and extract key information.

    EVENT TYPES (choose most appropriate):
    - "violence": Armed attacks, gang violence, shootings, killings, security incidents
    - "displacement": People forced to leave homes, evacuations, refugee movements
    - "kidnapping": Abductions, hostage situations
    - "school_closure": Schools closed due to security, strikes, issues
    - "school_destruction": Schools damaged, destroyed, attacked
    - "aid_needed": Humanitarian assistance requests, supply needs
    - "health_crisis": Medical emergencies, disease outbreaks, healthcare issues
    - "food_insecurity": Hunger, malnutrition, food shortages
    - "child_recruitment": Children recruited by armed groups
    - "protest": Demonstrations, civil unrest
    - "other": If none clearly apply

    LOCATION: Extract the most specific Haiti location mentioned (neighborhood, city, commune, department).
    
    SEVERITY: Rate crisis severity (1-5): 1=Minor, 2=Local concern, 3=Significant, 4=Major crisis, 5=Emergency

    Return ONLY a valid JSON object with these exact keys: "event_type", "location", "severity"

    TEXT: "{raw_text}"
    """
    
    safety_settings = [
        {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
    ]
    
    for i in range(retries):
        try:
            # Use Gemini Pro model
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt, safety_settings=safety_settings)
            result = response.text.strip()
            
            # Clean JSON response
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            # Parse and validate JSON
            parsed = json.loads(result)
            
            # Ensure we have a dict, not a list
            if isinstance(parsed, list):
                if len(parsed) > 0 and isinstance(parsed[0], dict):
                    parsed = parsed[0]
                else:
                    return {"event_type": "other", "location": "", "severity": 3}
            
            # Validate and clean response
            event_type = parsed.get("event_type", "other")
            if isinstance(event_type, list):
                event_type = event_type[0] if event_type else "other"
            
            location = parsed.get("location", "")
            if isinstance(location, list):
                location = location[0] if location else ""
            
            severity = parsed.get("severity", 3)
            if not isinstance(severity, int) or severity < 1 or severity > 5:
                severity = 3
                
            return {
                "event_type": str(event_type),
                "location": str(location),
                "severity": int(severity)
            }
            
        except Exception as e:
            print(f"Gemini attempt {i+1} failed: {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                return {"event_type": "other", "location": "", "severity": 3}

def get_location_coordinates(location_text):
    """Get coordinates for location from knowledge base"""
    if not location_text:
        return None, None
    
    # Check knowledge base first
    local_match = find_specific_haiti_location(location_text)
    if local_match:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT latitude, longitude FROM location_hierarchy 
                WHERE location_name = ? LIMIT 1
            """, (local_match['name'],))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result['latitude'], result['longitude']
        except Exception as e:
            print(f"Database lookup failed: {e}")
    
    return None, None

def process_and_store_report(raw_text, source_name=None, content_type=None, created_date=None, report_url=None):
    """Main function to process and store reports with Gemini Pro"""
    print(f"Processing: {raw_text[:80]}...")
    
    # Find local location
    local_location = find_specific_haiti_location(raw_text)
    if local_location:
        print(f"Found local location: {local_location['name']} ({local_location['type']})")
    
    # Process with Gemini Pro
    ai_result = process_with_gemini_pro(raw_text)
    
    # Determine final values
    event_type = ai_result.get("event_type", "other")
    ai_location = ai_result.get("location", "")
    severity = ai_result.get("severity", 3)
    
    # Use most specific location
    final_location = ai_location
    if local_location and (not ai_location or len(local_location['name']) > len(ai_location)):
        final_location = local_location['name']
    
    # Get coordinates
    latitude, longitude = get_location_coordinates(final_location)
    location_coords = f"{latitude},{longitude}" if latitude and longitude else None
    
    # Build metadata
    location_metadata = json.dumps({
        "type": local_location["type"] if local_location else "unknown",
        "parent": local_location["parent"] if local_location else "",
        "precision": "high" if local_location else "medium" if final_location else "low"
    })
    
    print(f"Classified as: {event_type}")
    print(f"Location: {final_location or 'None'}")
    print(f"Severity: {severity}/5")
    if location_coords:
        print(f"Coordinates: {location_coords}")
    
    # Store in database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reports (
                timestamp, raw_text, title, event_type, location_text,
                location_coords, latitude, longitude, location_metadata,
                source_name, content_type, severity, report_url, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            raw_text,
            raw_text[:100] + "..." if len(raw_text) > 100 else raw_text,
            event_type,
            final_location,
            location_coords,
            latitude,
            longitude,
            location_metadata,
            source_name or "Manual Input",
            content_type or "manual",
            severity,
            report_url,
            created_date or datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        print("Successfully stored in database\n")
        return True
        
    except Exception as e:
        print(f"Database error: {e}")
        return False

if __name__ == "__main__":
    # Test with sample reports
    test_reports = [
        "Gang violence has forced the closure of three schools in Cité Soleil, affecting over 1,200 children.",
        "Armed groups have taken control of several buildings in the Martissant neighborhood.",
        "UNICEF reports severe malnutrition cases in the Village de Dieu slum area.",
        "Ten children were killed in gang violence in Port-au-Prince this week."
    ]
    
    print("Testing processor with Gemini Pro...")
    for report in test_reports:
        success = process_and_store_report(report)
        print("-" * 50)