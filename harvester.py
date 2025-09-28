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

class HaitiCrisisHarvester:
    def __init__(self, app_name="haiti-crisis-dashboard"):
        self.base_url = "https://api.reliefweb.int/v1"
        self.app_name = app_name
        self.session = requests.Session()
        self.geolocator = Nominatim(user_agent="haiti_crisis_app")
        print(f"Initialized Haiti Crisis Harvester: '{app_name}'")
        
        # Focus only on reports - removed problematic content types
        self.content_types = {
            'reports': 'Reports and analysis from humanitarian organizations'
        }
        
        # Haiti locations for detection
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

        # Broader keywords for better classification
        self.crisis_keywords = [
            'gang', 'violence', 'shooting', 'kidnap', 'abduction', 'armed', 'conflict',
            'clash', 'gunfire', 'assassination', 'homicide', 'extortion', 'looting',
            'blockade', 'roadblock', 'insecurity', 'attack', 'crossfire', 'rape',
            'sexual violence', 'displacement', 'displaced', 'refugee', 'evacuation',
            'school', 'education', 'children', 'humanitarian', 'crisis', 'emergency',
            'food', 'hunger', 'malnutrition', 'health', 'medical', 'aid', 'assistance',
            'cholera', 'disease', 'outbreak', 'protest', 'demonstration'
        ]

    def get_db_connection(self):
        conn = sqlite3.connect('reports.db')
        conn.row_factory = sqlite3.Row
        return conn

    def get_haiti_reports(self, days_back=7, limit=50):
        """Fetch Haiti reports from ReliefWeb API"""
        endpoint = f"{self.base_url}/reports"
        
        params = {
            "appname": self.app_name,
            "filter[field]": "country",
            "filter[value]": "Haiti",
            "sort[]": "date:desc",
            "fields[include][]": [
                "id", "title", "body", "url_alias", "date.created", "date.original",
                "source.name", "theme.name", "format.name", "language.name"
            ],
            "limit": limit
        }

        try:
            print(f"Fetching Haiti reports from ReliefWeb...")
            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            content_items = data.get('data', [])
            print(f"Fetched {len(content_items)} reports")
            return content_items
            
        except Exception as e:
            print(f"Error fetching reports: {e}")
            return []

    def extract_report_text(self, item):
        """Extract text from ReliefWeb report"""
        if not isinstance(item, dict):
            print(f"Skipping invalid report entry")
            return None
        
        fields = item.get('fields', {})
        title = fields.get('title', '')
        body = fields.get('body', '')
        
        # Get dates - prefer original publication date
        date_dict = fields.get('date', {}) or {}
        created_date = date_dict.get('original') or date_dict.get('created', '')
        
        # Get source
        source = 'ReliefWeb Report'
        if 'source' in fields and fields['source']:
            if isinstance(fields['source'], list):
                source = fields['source'][0].get('name', source)
            elif isinstance(fields['source'], dict):
                source = fields['source'].get('name', source)

        # Create full text
        full_text = f"{title}. {body}" if body else title
        if source and source != 'ReliefWeb Report':
            full_text = f"Source: {source}. {full_text}"

        return {
            'text': full_text.strip(),
            'title': title,
            'source': source,
            'content_type': 'reports',
            'created_date': created_date,
            'url': f"https://reliefweb.int{fields.get('url_alias', '')}"
        }

    def classify_with_gemini_pro(self, text):
        """Use Gemini Pro to classify report"""
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

        LOCATION: Most specific Haiti location mentioned (neighborhood > city > department).
        
        SEVERITY: Crisis severity (1-5): 1=Minor, 2=Local, 3=Significant, 4=Major, 5=Emergency

        Return ONLY a valid JSON object: {{"event_type": "...", "location": "...", "severity": 1-5}}

        TEXT: "{text}"
        """
        
        safety_settings = [
            {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
            {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
        ]

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
            
            # Parse JSON
            parsed = json.loads(result)
            
            # Handle if response is a list instead of dict
            if isinstance(parsed, list):
                if len(parsed) > 0 and isinstance(parsed[0], dict):
                    parsed = parsed[0]
                else:
                    return None
            
            # Validate response structure
            event_type = parsed.get('event_type', 'other')
            if isinstance(event_type, list):
                event_type = event_type[0] if event_type else 'other'
            
            location = parsed.get('location', '')
            if isinstance(location, list):
                location = location[0] if location else ''
            
            severity = parsed.get('severity', 3)
            if not isinstance(severity, int) or severity < 1 or severity > 5:
                severity = 3
            
            return {
                'event_type': str(event_type),
                'location': str(location),
                'severity': int(severity)
            }
            
        except Exception as e:
            print(f"AI classification failed: {e}")
            return None

    def detect_location_fallback(self, text):
        """Simple location detection using text matching"""
        text_lower = text.lower()
        for location in self.haiti_locations:
            if location.lower() in text_lower:
                return location
        return None

    def classify_event_fallback(self, text):
        """Simple keyword-based event classification"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['school', 'education']):
            if any(word in text_lower for word in ['closed', 'closure', 'fermé']):
                return 'school_closure'
            elif any(word in text_lower for word in ['destroyed', 'attack', 'damage']):
                return 'school_destruction'
        
        if any(word in text_lower for word in ['violence', 'gang', 'armed', 'shooting', 'attack']):
            return 'violence'
        
        if any(word in text_lower for word in ['kidnap', 'abduction']):
            return 'kidnapping'
        
        if any(word in text_lower for word in ['displacement', 'displaced', 'flee']):
            return 'displacement'
        
        if any(word in text_lower for word in ['food', 'hunger', 'malnutrition']):
            return 'food_insecurity'
        
        if any(word in text_lower for word in ['health', 'medical', 'cholera', 'disease']):
            return 'health_crisis'
        
        if any(word in text_lower for word in ['aid', 'assistance', 'humanitarian']):
            return 'aid_needed'
        
        if any(word in text_lower for word in ['child', 'children', 'recruit']):
            return 'child_recruitment'
        
        if any(word in text_lower for word in ['protest', 'demonstration']):
            return 'protest'
        
        return 'other'

    def get_coordinates(self, location_text):
        """Get coordinates for location"""
        if not location_text:
            return None
            
        try:
            location = self.geolocator.geocode(f"{location_text}, Haiti", timeout=10)
            if location:
                return f"{location.latitude},{location.longitude}"
        except Exception as e:
            print(f"Geocoding failed for {location_text}: {e}")
        
        return None

    def is_relevant_content(self, text):
        """Check if content is relevant to Haiti crisis monitoring"""
        text_lower = text.lower()
        
        # More inclusive - include any mention of crisis keywords or Haiti-specific content
        return (
            any(keyword in text_lower for keyword in self.crisis_keywords) or
            'haiti' in text_lower or
            any(location.lower() in text_lower for location in self.haiti_locations)
        )

    def process_single_report(self, content_data):
        """Process one report with AI and fallbacks"""
        if not content_data:
            return None

        text = content_data['text']
        
        if len(text) < 20:
            return None

        print(f"Processing report: {text[:80]}...")

        # Check if content is relevant
        if not self.is_relevant_content(text):
            print("Content not relevant to Haiti crisis - skipping")
            return None

        # Try AI classification first
        ai_result = self.classify_with_gemini_pro(text)

        if ai_result and isinstance(ai_result, dict):
            event_type = ai_result.get('event_type', 'other')
            location_text = ai_result.get('location', '')
            severity = ai_result.get('severity', 3)
            print(f"AI: {event_type} (severity {severity}), {location_text or 'no location'}")
        else:
            # Fallback classification
            event_type = self.classify_event_fallback(text)
            location_text = self.detect_location_fallback(text)
            severity = 3
            print(f"Fallback: {event_type} (severity {severity}), {location_text or 'no location'}")

        # Get coordinates
        coordinates = self.get_coordinates(location_text) if location_text else None
        if coordinates:
            print(f"Coordinates: {coordinates}")

        return {
            'text': text,
            'title': content_data['title'],
            'event_type': event_type,
            'location_text': location_text,
            'location_coords': coordinates,
            'source': content_data['source'],
            'content_type': content_data['content_type'],
            'severity': severity,
            'created_date': content_data['created_date'],
            'url': content_data['url']
        }

    def store_report(self, processed_data):
        """Store processed report in database"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Add missing columns if they don't exist
            columns_to_add = [
                ("source_name", "TEXT"),
                ("content_type", "TEXT"), 
                ("severity", "INTEGER DEFAULT 3"),
                ("title", "TEXT"),
                ("report_url", "TEXT"),
                ("created_date", "TEXT"),
                ("location_coords", "TEXT")
            ]
            
            for column_name, column_type in columns_to_add:
                try:
                    cursor.execute(f"ALTER TABLE reports ADD COLUMN {column_name} {column_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            
            conn.commit()
            
            # Check for duplicates by URL
            if processed_data.get('url'):
                cursor.execute("SELECT 1 FROM reports WHERE report_url = ? LIMIT 1", (processed_data['url'],))
                if cursor.fetchone():
                    conn.close()
                    return False

            # Insert new report
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

    def harvest_reports(self, days_back=7, limit=50):
        """Main harvesting method"""
        print("="*70)
        print("HAITI CRISIS DASHBOARD - HARVESTING WITH GEMINI PRO")
        print("="*70)
        
        # Get reports from API
        raw_reports = self.get_haiti_reports(days_back, limit)
        
        if not raw_reports:
            print("No reports found")
            return
        
        # Process each report
        total_processed = 0
        total_stored = 0
        total_classified = 0
        total_located = 0
        
        print(f"\nProcessing {len(raw_reports)} reports...")
        
        for i, report in enumerate(raw_reports, 1):
            try:
                # Extract report data
                content_data = self.extract_report_text(report)
                
                if not content_data:
                    continue
                
                total_processed += 1
                
                # Process with AI and fallbacks
                processed = self.process_single_report(content_data)
                
                if processed:
                    # Track statistics
                    if processed['event_type'] != 'other':
                        total_classified += 1
                    if processed['location_text']:
                        total_located += 1
                    
                    # Store in database
                    if self.store_report(processed):
                        total_stored += 1
                        print(f"Report {i} stored successfully")
                    else:
                        print(f"Report {i} failed to store (duplicate or error)")
                else:
                    print(f"Report {i} was not relevant or too short")
                
                time.sleep(0.5)  # Be respectful to APIs
                
            except Exception as e:
                print(f"Error processing report {i}: {e}")
                continue
        
        # Final statistics
        print(f"\n" + "="*70)
        print("HARVEST COMPLETE!")
        print("="*70)
        print(f"Reports fetched: {len(raw_reports)}")
        print(f"Reports processed: {total_processed}")
        print(f"Reports stored: {total_stored}")
        print(f"Successfully classified (not 'other'): {total_classified}")
        print(f"Locations found: {total_located}")
        if total_processed > 0:
            print(f"Storage success rate: {total_stored/total_processed*100:.1f}%")
        print("="*70)

if __name__ == "__main__":
    harvester = HaitiCrisisHarvester()
    harvester.harvest_reports(days_back=7, limit=20)
