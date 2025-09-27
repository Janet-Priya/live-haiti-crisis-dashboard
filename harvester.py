import requests
import json
import time
import sqlite3
import os
from datetime import datetime
from geopy.geocoders import Nominatim
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment and configure Gemini
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

class ComprehensiveHaitiHarvester:
    def __init__(self, app_name="haiti-crisis-dashboard"):
        self.base_url = "https://api.reliefweb.int/v1"
        self.app_name = app_name
        self.session = requests.Session()
        self.geolocator = Nominatim(user_agent="haiti_crisis_app")
        print(f"Initialized comprehensive harvester: '{app_name}'")
        
        self.content_types = {
            'reports': 'Reports and analysis from humanitarian organizations',
            'disasters': 'Disaster declarations and emergency information', 
            'blog': 'Blog posts and opinion pieces',
            'references': 'Reference materials and guides'
        }
        
        self.haiti_locations = [
            'Cité Soleil', 'Cite Soleil', 'Martissant', 'Bel Air', 'Belair',
            'Delmas', 'Pétion-Ville', 'Petion-Ville', 'Carrefour', 'Tabarre',
            'Croix-des-Bouquets', 'Croix des Bouquets', 'Port-au-Prince',
            'Gonaïves', 'Gonaives', 'Cap-Haïtien', 'Cap-Haitien', 'Saint-Marc',
            'Les Cayes', 'Jacmel', 'Jérémie', 'Jeremie', 'Hinche',
            'La Saline', 'Village de Dieu', 'Boston', 'Léogâne', 'Leogane',
            'Artibonite', 'Nord', 'Sud', 'Ouest', 'Centre', 'Nippes', 'Sud-Est',
            'Nord-Est', 'Grande-Anse', 'Miragoâne', 'Miragoane'
        ]

        # Simple keyword sets to identify conflict vs natural disasters
        self.conflict_keywords = [
            'gang', 'shooting', 'kidnap', 'abduction', 'armed', 'conflict', 'clash',
            'gunfire', 'assassination', 'homicide', 'extortion', 'looting', 'blockade',
            'roadblock', 'insecurity', 'violence', 'attack', 'crossfire', 'rape', 'sexual violence'
        ]
        self.disaster_keywords = [
            'earthquake', 'tremor', 'flood', 'hurricane', 'storm', 'cyclone', 'tropical storm',
            'landslide', 'mudslide', 'rainstorm', 'drought', 'wildfire', 'tsunami', 'aftershock'
        ]

    # --- DATABASE CONNECTION ---
    def get_db_connection(self):
        conn = sqlite3.connect('reports.db')
        conn.row_factory = sqlite3.Row
        return conn

    # --- FETCH CONTENT ---
    def get_haiti_content(self, content_type, days_back=7, limit=50):
        endpoint = f"{self.base_url}/{content_type}"
        
        base_params = {
            "appname": self.app_name,
            "limit": limit,
            "sort[]": "date:desc"
        }
        
        if content_type == 'reports':
            params = {
                **base_params,
                "filter[field]": "country",
                "filter[value]": "Haiti",
                "fields[include][]": [
                    "id", "title", "body", "url_alias", "date.created", "date.original",
                    "source.name", "theme.name", "format.name", "language.name"
                ]
            }
        elif content_type == 'blog':
            params = {
                **base_params,
                "filter[field]": "theme",
                "filter[value]": "Haiti",  
                "fields[include][]": [
                    "id", "title", "body", "url_alias", "date.created",
                    "source.name", "theme.name"
                ]
            }
        elif content_type == 'references':
            params = {
                **base_params,
                "query[value]": "Haiti",
                "fields[include][]": [
                    "id", "title", "body", "url_alias", "date.created",
                    "source.name", "theme.name"
                ]
            }
        else:
            params = {
                **base_params,
                "query[value]": "Haiti",
                "fields[include][]": ["id", "title", "body", "date.created"]
            }

        try:
            print(f"Fetching {content_type} from ReliefWeb...")
            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            content_items = data.get('data', [])
            print(f"Fetched {len(content_items)} {content_type}")
            return content_items, content_type
            
        except Exception as e:
            print(f"Error fetching {content_type}: {e}")
            return [], content_type

    # --- EXTRACT TEXT ---
    def extract_content_text(self, item, content_type):
        if not isinstance(item, dict):
            print(f"Skipping invalid {content_type} entry: {item}")
            return None
        
        fields = item.get('fields', {})
        
        if content_type == 'disasters':
            title = fields.get('name', '')
            body = fields.get('description', '')
            date_created = fields.get('date', {}).get('created', '')
            source = 'ReliefWeb Disasters'
        else:
            title = fields.get('title', '')
            body = fields.get('body', '')
            date_dict = fields.get('date', {}) or {}
            # Prefer original publication date when present
            date_created = date_dict.get('original') or date_dict.get('created', '')
            
            source = content_type.title()
            if 'source' in fields and fields['source']:
                if isinstance(fields['source'], list):
                    source = fields['source'][0].get('name', source)
                elif isinstance(fields['source'], dict):
                    source = fields['source'].get('name', source)

        full_text = f"{title}. {body}" if body else title
        if source and source != content_type.title():
            full_text = f"Source: {source}. {full_text}"

        return {
            'text': full_text.strip(),
            'title': title,
            'source': source,
            'content_type': content_type,
            'created_date': date_created,
            'url': f"https://reliefweb.int{fields.get('url_alias', '')}"
        }

    # --- AI CLASSIFICATION ---
    def classify_with_enhanced_ai(self, text, content_type):
        prompt = f"""
        Analyze this Haiti humanitarian content from {content_type} and extract key information.

        Focus on giving the most specific Haitian location possible, e.g., city, town, commune, or department. 
        If only "Haiti" is mentioned, try to infer a more precise location from context.

        Return ONLY JSON: {{"event_type": "...", "location": "...", "severity": 1-5}}

        Text: "{text}"
        """
        safety_settings = [
            {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        ]

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt, safety_settings=safety_settings)
            result = response.text.strip()
            
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(result)
            severity = parsed.get('severity', 3)
            if not isinstance(severity, int) or severity < 1 or severity > 5:
                severity = 3
            parsed['severity'] = severity
            return parsed
            
        except Exception as e:
            print(f"AI classification failed: {e}")
            return None

    # --- FALLBACK LOCATION DETECTION ---
    def detect_location_fallback(self, text):
        text_lower = text.lower()
        for loc in self.haiti_locations:
            if loc.lower() in text_lower:
                return loc
        return None

    # --- PROCESS SINGLE ITEM ---
    def process_single_item(self, content_data):
        if not content_data:
            return None

        text = content_data['text']
        content_type = content_data['content_type']

        if len(text) < 20:
            return None

        print(f"Processing {content_type}: {text[:80]}...")

        ai_result = self.classify_with_enhanced_ai(text, content_type)

        if ai_result and isinstance(ai_result, dict):
            event_type = ai_result.get('event_type', 'other')
            if isinstance(event_type, list):
                event_type = ", ".join(event_type)

            location_text = ai_result.get('location', '')
            severity = ai_result.get('severity', 3)

            if location_text.strip().lower() == "haiti" or not location_text.strip():
                fallback_loc = self.detect_location_fallback(text)
                if fallback_loc:
                    location_text = fallback_loc

            print(f"AI: {event_type} (severity {severity}), {location_text or 'no location'}")
        else:
            event_type = "other"
            severity = 3
            location_text = self.detect_location_fallback(text) or ""
            print(f"Fallback: {event_type} (severity {severity}), {location_text or 'no location'}")

        coordinates = self.get_coordinates(location_text) if location_text else None
        if coordinates:
            print(f"Coordinates: {coordinates}")

        # Normalize event type to focus on human conflict; skip natural disasters
        normalized_event = self.normalize_event_type(event_type, text)
        if not self.is_conflict_related(normalized_event, text):
            return None

        return {
            'text': text,
            'title': content_data['title'],
            'event_type': normalized_event,
            'location_text': location_text,
            'location_coords': coordinates,
            'source': content_data['source'],
            'content_type': content_type,
            'severity': severity,
            'created_date': content_data['created_date'],
            'url': content_data['url']
        }

    # --- GEOCODING ---
    def get_coordinates(self, location_text):
        if not location_text:
            return None
        try:
            location = self.geolocator.geocode(f"{location_text}, Haiti", timeout=10)
            if location:
                return f"{location.latitude},{location.longitude}"
        except Exception as e:
            print(f"Geocoding failed for {location_text}: {e}")
        return None

    # --- STORE CONTENT IN DB ---
    def store_content(self, processed_data):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("ALTER TABLE reports ADD COLUMN source_name TEXT")
                cursor.execute("ALTER TABLE reports ADD COLUMN content_type TEXT")
                cursor.execute("ALTER TABLE reports ADD COLUMN severity INTEGER")
                cursor.execute("ALTER TABLE reports ADD COLUMN title TEXT")
                cursor.execute("ALTER TABLE reports ADD COLUMN report_url TEXT")
                cursor.execute("ALTER TABLE reports ADD COLUMN created_date TEXT")
                cursor.execute("ALTER TABLE reports ADD COLUMN location_coords TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass
            
            # De-duplication by report_url
            if processed_data.get('url'):
                cursor.execute("SELECT 1 FROM reports WHERE report_url = ? LIMIT 1", (processed_data['url'],))
                if cursor.fetchone():
                    conn.close()
                    return False

            cursor.execute("""
                INSERT INTO reports (
                    timestamp, raw_text, title, event_type, location_text, 
                    location_coords, source_name, content_type, severity,
                    report_url, created_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                processed_data['text'],
                processed_data['title'],
                processed_data['event_type'],
                processed_data['location_text'],
                processed_data['location_coords'],
                processed_data['source'],
                processed_data['content_type'],
                processed_data['severity'],
                processed_data['url'],
                processed_data['created_date']
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Database error: {e}")
            return False

    # --- EVENT NORMALIZATION / FILTERING ---
    def normalize_event_type(self, event_type, text):
        if not event_type:
            return 'other'
        e = str(event_type).lower()
        # Map common variants to a focused set
        mapping = {
            'violence': 'violence',
            'armed_violence': 'violence',
            'attack': 'violence',
            'shooting': 'violence',
            'kidnapping': 'kidnapping',
            'kidnap': 'kidnapping',
            'abduction': 'kidnapping',
            'sexual_violence': 'sexual_violence',
            'rape': 'sexual_violence',
            'displacement': 'displacement',
            'protest': 'protest',
            'looting': 'looting',
            'roadblock': 'roadblock',
        }
        # Disaster cues to filter out
        disasters = ['earthquake', 'flood', 'hurricane', 'storm', 'cyclone', 'landslide', 'drought', 'tsunami']
        if any(d in e for d in disasters) or any(d in text.lower() for d in self.disaster_keywords):
            return 'natural_disaster'
        for key, value in mapping.items():
            if key in e:
                return value
        # Keyword based inference
        if any(k in text.lower() for k in self.conflict_keywords):
            return 'violence'
        return e or 'other'

    def is_conflict_related(self, normalized_event_type, text):
        if normalized_event_type == 'natural_disaster':
            return False
        if normalized_event_type in ['violence', 'kidnapping', 'sexual_violence', 'displacement', 'protest', 'looting', 'roadblock']:
            return True
        return any(k in text.lower() for k in self.conflict_keywords)

    # --- HARVEST ALL CONTENT ---
    def harvest_all_content(self, days_back=7, limit_per_type=30):
        print("="*70)
        print("HAITI CRISIS DASHBOARD - COMPREHENSIVE MULTI-FORMAT HARVEST")
        print("="*70)
        
        total_success = 0
        total_items = 0
        total_eligible = 0
        type_stats = {}
        
        for content_type, description in self.content_types.items():
            # Skip ReliefWeb 'disasters' content type to focus on human conflict
            if content_type == 'disasters':
                continue
            print(f"\n--- HARVESTING {content_type.upper()} ---")
            print(f"Description: {description}")
            
            content_items, _ = self.get_haiti_content(content_type, days_back, limit_per_type)
            if not content_items:
                print(f"No {content_type} found, skipping...")
                continue
            
            type_success = 0
            type_classified = 0
            type_located = 0
            type_eligible = 0
            
            for i, item in enumerate(content_items, 1):
                try:
                    content_data = self.extract_content_text(item, content_type)
                    processed = self.process_single_item(content_data)
                    
                    # Count only conflict-eligible items for success rate
                    if content_data:
                        # A rough eligibility: contains conflict keywords or will normalize to conflict
                        raw_text_lower = content_data['text'].lower()
                        if any(k in raw_text_lower for k in self.conflict_keywords):
                            type_eligible += 1

                    if processed:
                        if processed['event_type'] != 'other':
                            type_classified += 1
                        if processed['location_text']:
                            type_located += 1
                        
                        if self.store_content(processed):
                            type_success += 1
                            print(f"{content_type} {i} stored successfully")
                    
                    total_items += 1
                    time.sleep(0.3)
                    
                except Exception as e:
                    print(f"Error processing {content_type} {i}: {e}")
                    continue
            
            type_stats[content_type] = {
                'total': len(content_items),
                'stored': type_success,
                'classified': type_classified,
                'located': type_located,
                'eligible': type_eligible
            }
            total_success += type_success
            total_eligible += type_eligible
        
        print(f"\n" + "="*70)
        print("COMPREHENSIVE HARVEST COMPLETE!")
        print("="*70)
        
        for content_type, stats in type_stats.items():
            print(f"\n{content_type.upper()}:")
            print(f"  Total items: {stats['total']}")
            print(f"  Successfully stored: {stats['stored']}")
            print(f"  Classified (not 'other'): {stats['classified']}")
            print(f"  Locations found: {stats['located']}")
            if stats['eligible'] > 0:
                print(f"  Success rate (eligible conflict): {stats['stored']/stats['eligible']*100:.1f}%")
            elif stats['total'] > 0:
                print(f"  Success rate: {stats['stored']/stats['total']*100:.1f}%")
        
        print(f"\nOVERALL SUMMARY:")
        print(f"Total content items processed: {total_items}")
        print(f"Total successfully stored: {total_success}")
        if total_eligible > 0:
            print(f"Overall success rate (eligible conflict): {total_success/total_eligible*100:.1f}%")
        else:
            print(f"Overall success rate: {total_success/total_items*100:.1f}%" if total_items > 0 else "No items processed")
        print("="*70)


if __name__ == "__main__":
    harvester = ComprehensiveHaitiHarvester()
    
    harvester.harvest_all_content(days_back=7, limit_per_type=20)
