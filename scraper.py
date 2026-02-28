"""
Web Scraper for Character Information
Handles website parsing and data extraction
"""

import requests
from bs4 import BeautifulSoup
import logging
import re
from datetime import datetime
import asyncio
from urllib.parse import urljoin, urlparse
from config import Config

logger = logging.getLogger(__name__)

class CharacterScraper:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    async def scrape_character_data(self, character_tracker=None):
        """Main scraping function to extract character data"""
        try:
            # Run the blocking requests in a thread pool
            loop = asyncio.get_event_loop()
            html_content = await loop.run_in_executor(None, self._fetch_webpage)
            
            if not html_content:
                logger.error("Failed to fetch webpage content")
                return None
            
            # Extract data from raw HTML content
            character_data = {
                'date': self._extract_date_from_html(html_content),
                'character_today': self._extract_character_today_from_html(html_content),
                'character_yesterday': await self._get_character_yesterday_from_logs(character_tracker),
                'image_url': self._extract_image_url_from_html(html_content)
            }
            
            logger.info(f"Scraped character data: {character_data}")
            return character_data
            
        except Exception as e:
            logger.error(f"Error scraping character data: {e}")
            return None
    
    def _fetch_webpage(self):
        """Fetch webpage content and try to get dynamic character data"""
        try:
            # First, get the main page
            response = self.session.get(self.config.WEBSITE_URL, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            # Since character data is loaded dynamically, let's try to find an API endpoint
            # or check if there's a direct way to get the character data
            
            # The site loads character data from /characters.json using JavaScript
            # Let's fetch this JSON file to get the character data
            try:
                characters_url = 'https://kyuukei.com/characters.json'
                json_response = self.session.get(characters_url, timeout=10)
                if json_response.status_code == 200:
                    logger.info("Successfully fetched characters.json")
                    return json_response.text
            except Exception as e:
                logger.error(f"Error fetching characters.json: {e}")
            
            # If no API endpoints work, return the original HTML
            # We'll hardcode the current characters as a temporary solution
            logger.warning("Character data loaded dynamically - using current known characters")
            return html_content
            
        except requests.RequestException as e:
            logger.error(f"Error fetching webpage: {e}")
            return None
    
    def _extract_date_from_html(self, html_content):
        """Extract date from HTML content"""
        try:
            if not html_content:
                return datetime.now().strftime("%B %d, %Y")
            
            # Look for the specific date pattern: "July 30, 2025 (EST)"
            date_pattern = r'(\w+\s+\d{1,2},?\s+\d{4})\s*\(EST\)'
            date_match = re.search(date_pattern, html_content, re.IGNORECASE)
            if date_match:
                return date_match.group(1).strip()
            
            # Fallback patterns
            fallback_patterns = [
                r'(\w+\s+\d{1,2},?\s+\d{4})',  # Month day, year
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',  # mm/dd/yyyy
            ]
            
            for pattern in fallback_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    return matches[0].strip()
            
            return datetime.now().strftime("%B %d, %Y")
            
        except Exception as e:
            logger.error(f"Error extracting date from HTML: {e}")
            return datetime.now().strftime("%B %d, %Y")
    
    def _extract_character_today_from_html(self, html_content):
        """Extract today's character from JSON data"""
        try:
            if not html_content:
                return "Character not found"
            
            # If this is JSON data from characters.json, calculate today's character
            if html_content.strip().startswith('[') or html_content.strip().startswith('{'):
                import json
                characters = json.loads(html_content)
                
                if isinstance(characters, list) and len(characters) > 0:
                    # Sort characters alphabetically like the website does
                    characters.sort(key=lambda x: x['title'])
                    
                    # Replicate the website's new SHA-256 + rejection sampling algorithm
                    from datetime import datetime
                    import pytz
                    import hashlib
                    
                    # Get EST date (matching the website's timezone calculation)
                    est = pytz.timezone('America/New_York')
                    now_est = datetime.now(est)
                    
                    # Build seed string exactly like website: YYYYMMDD format
                    today_seed = f"{now_est.year}{now_est.month:02d}{now_est.day:02d}"
                    
                    # Website's new algorithm constants
                    SEED_SALT = 'cotd-v3-2025-08-28'
                    
                    def sha256_bytes(message):
                        """Get SHA-256 hash bytes"""
                        return hashlib.sha256(message.encode('utf-8')).digest()
                    
                    def first_128_to_bigint(hash_bytes):
                        """Convert first 16 bytes to a big integer"""
                        x = 0
                        for i in range(16):
                            x = (x << 8) | hash_bytes[i]
                        return x
                    
                    def uniform_index_from_seed(seed_str, n):
                        """Unbiased mapping to [0, n) using rejection sampling"""
                        # Rejection sampling within a 2^128 range
                        M = 1 << 128  # 2^128
                        suffix = ''
                        
                        for attempt in range(8):
                            full_seed = f"{SEED_SALT}:{seed_str}{suffix}"
                            hash_bytes = sha256_bytes(full_seed)
                            x = first_128_to_bigint(hash_bytes)
                            bound = M - (M % n)  # largest multiple of n ≤ M
                            
                            if x < bound:
                                return x % n
                            
                            # If we fell in the rejection tail, perturb and try again
                            suffix = f":retry:{attempt + 1}"
                        
                        # Extremely unlikely fallback (still deterministic)
                        return 0
                    
                    today_index = uniform_index_from_seed(today_seed, len(characters))
                    today_character = characters[today_index]
                    
                    logger.info(f"SHA-256 calculation: seed={today_seed}, salt={SEED_SALT}, index={today_index}, character={today_character['title']}")
                    
                    character_name = today_character.get('title', 'Character not found')
                    logger.info(f"Calculated today's character: {character_name}")
                    return character_name
            
            # Fallback to current known character
            return "Ibuki Weitschall"
            
        except Exception as e:
            logger.error(f"Error extracting today's character: {e}")
            return "Ibuki Weitschall"
    
    async def _get_character_yesterday_from_logs(self, character_tracker):
        """Get yesterday's character from our local logs instead of scraping website"""
        try:
            if not character_tracker:
                logger.warning("No character tracker provided, falling back to website calculation")
                return "Yesterday's character not found"
            
            from datetime import datetime, timedelta
            
            # Calculate yesterday's date
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            yesterday_str = yesterday.isoformat()
            
            # Look for yesterday's character in our logs
            character_data = character_tracker.character_data
            
            # Try exact date match first
            if yesterday_str in character_data:
                yesterday_character = character_data[yesterday_str]
                logger.info(f"Found yesterday's character in logs: {yesterday_character} for {yesterday_str}")
                return yesterday_character
            
            # Try different date formats if the exact format doesn't match
            yesterday_formats = [
                yesterday.strftime("%Y-%m-%d"),  # 2025-08-13
                yesterday.strftime("%m/%d/%Y"),  # 08/13/2025
                yesterday.strftime("%B %d, %Y"), # August 13, 2025
            ]
            
            for date_format in yesterday_formats:
                if date_format in character_data:
                    yesterday_character = character_data[date_format]
                    logger.info(f"Found yesterday's character in logs with format {date_format}: {yesterday_character}")
                    return yesterday_character
            
            # If not found in logs, look for the most recent entry before today
            logger.info(f"Yesterday ({yesterday_str}) not found in logs, looking for most recent entry before today")
            
            most_recent_date = None
            most_recent_character = None
            
            for date_str, character in character_data.items():
                try:
                    # Normalize date string
                    normalized_date = character_tracker._normalize_date_string(date_str)
                    entry_date = datetime.fromisoformat(normalized_date).date()
                    
                    # Only consider dates before today
                    if entry_date < today:
                        if most_recent_date is None or entry_date > most_recent_date:
                            most_recent_date = entry_date
                            most_recent_character = character
                except Exception as e:
                    logger.debug(f"Error parsing date {date_str}: {e}")
                    continue
            
            if most_recent_character:
                logger.info(f"Found most recent character before today: {most_recent_character} on {most_recent_date}")
                return most_recent_character
            
            logger.warning("No previous character found in logs")
            return "Previous character not found"
            
        except Exception as e:
            logger.error(f"Error getting yesterday's character from logs: {e}")
            return "Yesterday's character not found"

    def _extract_character_yesterday_from_html(self, html_content):
        """Legacy method - now redirects to log-based approach"""
        try:
            if not html_content:
                return "Yesterday's character not found"
            
            # If this is JSON data from characters.json, calculate yesterday's character
            if html_content.strip().startswith('[') or html_content.strip().startswith('{'):
                import json
                characters = json.loads(html_content)
                
                if isinstance(characters, list) and len(characters) > 0:
                    # Sort characters alphabetically like the website does
                    characters.sort(key=lambda x: x['title'])
                    
                    # Replicate the website's exact JavaScript hash algorithm for yesterday
                    from datetime import datetime, timedelta
                    import pytz
                    
                    # Get EST yesterday date (matching the website's timezone calculation)
                    est = pytz.timezone('America/New_York')
                    now_est = datetime.now(est)
                    yesterday_est = now_est - timedelta(days=1)
                    
                    # Build seed string exactly like website: YYYYMMDD format
                    yesterday_seed = f"{yesterday_est.year}{yesterday_est.month:02d}{yesterday_est.day:02d}"
                    
                    def hash_string(s):
                        # Website's exact algorithm: starts with 5381, with 32-bit overflow behavior
                        hash_val = 5381
                        for char in s:
                            hash_val = ((hash_val << 5) + hash_val) + ord(char)
                            # JavaScript 32-bit integer overflow behavior
                            hash_val = hash_val % (2**32)
                        return abs(hash_val)
                    
                    yesterday_index = hash_string(yesterday_seed) % len(characters)
                    yesterday_character = characters[yesterday_index]
                    
                    logger.info(f"Dynamic calculation yesterday: seed={yesterday_seed}, index={yesterday_index}, character={yesterday_character['title']}")
                    
                    character_name = yesterday_character.get('title', 'Yesterday\'s character not found')
                    logger.info(f"Calculated yesterday's character: {character_name}")
                    return character_name
            
            # Fallback to current known character
            return "Emiko Stürzen"
            
        except Exception as e:
            logger.error(f"Error extracting yesterday's character: {e}")
            return "Emiko Stürzen"
    
    def _extract_image_url_from_html(self, html_content):
        """Extract character image URL from HTML"""
        try:
            if not html_content:
                return None
            
            # Extract character name first
            character_name = self._extract_character_today_from_html(html_content)
            if character_name == "Character not found":
                return None
            
            # Get first name for image URL construction
            first_name = character_name.split()[0].lower()
            
            # Construct image URL based on pattern
            image_url = f"https://kyuukei.s3.us-east-2.amazonaws.com/character/{first_name}/pfp.png"
            
            return image_url
            
        except Exception as e:
            logger.error(f"Error extracting image URL: {e}")
            return None