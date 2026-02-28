"""
Birthday Scraper for Character Information
Handles scraping character birthdays from the website's _characters/ folder
"""

import requests
from bs4 import BeautifulSoup
import logging
import re
import json
import os
from datetime import datetime, timedelta
import asyncio
from config import Config

logger = logging.getLogger(__name__)

class BirthdayScraper:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.birthday_cache_file = "birthdays_cache.json"
        self.birthdays = {}
        
    async def get_character_birthdays(self):
        """Get all character birthdays, using cache if available"""
        try:
            # Load cached birthdays first
            self._load_birthday_cache()
            
            # Get fresh character list
            characters = await self._get_character_list()
            if not characters:
                logger.error("Failed to get character list")
                return self.birthdays
            
            # Check if we need to update any birthdays
            updated = False
            for character in characters:
                char_name = character.get('title', '')
                char_url = character.get('url', '')
                if char_name and char_name not in self.birthdays:
                    logger.info(f"Fetching birthday for new character: {char_name}")
                    birthday = await self._fetch_character_birthday(char_name, char_url)
                    if birthday:
                        self.birthdays[char_name] = birthday
                        updated = True
            
            # Save updated cache
            if updated:
                self._save_birthday_cache()
            
            return self.birthdays
            
        except Exception as e:
            logger.error(f"Error getting character birthdays: {e}")
            return self.birthdays
    
    async def get_character_list(self):
        """Get list of all characters from characters.json (public method)"""
        return await self._get_character_list()
    
    async def _get_character_list(self):
        """Get list of all characters from characters.json"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.session.get('https://kyuukei.com/characters.json', timeout=10)
            )
            
            if response.status_code == 200:
                characters = response.json()
                logger.info(f"Found {len(characters)} characters")
                return characters
            else:
                logger.error(f"Failed to fetch characters.json: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching character list: {e}")
            return None
    
    async def _fetch_character_birthday(self, character_name, character_url_path):
        """Fetch birthday for a specific character from their HTML page"""
        try:
            # Use the URL path from characters.json
            char_url = f'https://kyuukei.com{character_url_path}'
            
            loop = asyncio.get_event_loop()
            
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: self.session.get(char_url, timeout=10)
                )
                
                if response.status_code == 200:
                    content = response.text
                    birthday = self._extract_birthday_from_html(content)
                    if birthday:
                        logger.info(f"Found birthday for {character_name}: {birthday}")
                        return birthday
                    else:
                        # Check if birthday is marked as "TBD" or similar
                        logger.debug(f"No valid birthday found for {character_name} (may be TBD)")
                        return None
                else:
                    logger.warning(f"Failed to fetch page for {character_name}: {response.status_code}")
                    return None
                    
            except Exception as e:
                logger.debug(f"Failed to fetch {char_url}: {e}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching birthday for {character_name}: {e}")
            return None
    
    def _extract_birthday_from_html(self, content):
        """Extract birthday from HTML content"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for birthday in HTML - format: <p><strong>Birthday:</strong> April 7th</p>
            birthday_elements = soup.find_all('p')
            
            for element in birthday_elements:
                text = element.get_text()
                if 'Birthday:' in text:
                    # Extract the birthday part after "Birthday:"
                    birthday_match = re.search(r'Birthday:\s*(.+)', text, re.IGNORECASE)
                    if birthday_match:
                        birthday_str = birthday_match.group(1).strip()
                        
                        # Skip TBD or empty birthdays
                        if birthday_str.upper() in ['TBD', 'TO BE DETERMINED', 'UNKNOWN', '']:
                            return None
                        
                        # Parse the birthday string
                        parsed_birthday = self._parse_birthday_string(birthday_str)
                        if parsed_birthday:
                            return parsed_birthday
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting birthday from HTML: {e}")
            return None
    
    def _parse_birthday_string(self, birthday_str):
        """Parse birthday string into month/day format"""
        try:
            # Remove common prefixes/suffixes
            birthday_str = birthday_str.lower().strip()
            birthday_str = re.sub(r'\b(the\s+)?(\d+)(st|nd|rd|th)\b', r'\2', birthday_str)
            
            # Common date formats to try
            date_formats = [
                '%B %d',      # January 15
                '%b %d',      # Jan 15
                '%m/%d',      # 1/15
                '%m-%d',      # 1-15
                '%d/%m',      # 15/1 (European)
                '%d-%m',      # 15-1 (European)
                '%B %d, %Y',  # January 15, 1990 (ignore year)
                '%b %d, %Y',  # Jan 15, 1990 (ignore year)
            ]
            
            for fmt in date_formats:
                try:
                    if '%Y' in fmt:
                        # Parse with year but only keep month/day
                        parsed = datetime.strptime(birthday_str, fmt)
                        return f"{parsed.strftime('%B')} {parsed.day}"
                    else:
                        # Add a dummy year for parsing
                        test_str = f"{birthday_str} 2000"
                        test_fmt = f"{fmt} %Y"
                        parsed = datetime.strptime(test_str, test_fmt)
                        return f"{parsed.strftime('%B')} {parsed.day}"
                except ValueError:
                    continue
            
            # Manual parsing for common formats
            if re.match(r'^(\w+)\s+(\d{1,2})$', birthday_str):
                return birthday_str.title()
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing birthday string '{birthday_str}': {e}")
            return None
    
    def get_today_birthdays(self):
        """Get characters who have birthdays today"""
        try:
            today = datetime.now()
            today_str = today.strftime('%B %d').replace(' 0', ' ')  # Remove leading zero
            
            today_birthdays = []
            for char_name, birthday in self.birthdays.items():
                if birthday and birthday.replace(' 0', ' ') == today_str:
                    today_birthdays.append(char_name)
            
            return today_birthdays
            
        except Exception as e:
            logger.error(f"Error getting today's birthdays: {e}")
            return []
    
    def get_sorted_birthdays(self):
        """Get all birthdays sorted by calendar month/day order"""
        try:
            today = datetime.now()
            current_year = today.year
            
            birthday_list = []
            
            for char_name, birthday_str in self.birthdays.items():
                if not birthday_str:
                    continue
                
                try:
                    # Special handling for Feb 29 (leap year birthdays)
                    if birthday_str == "February 29":
                        # Calculate days until next Feb 29 (next leap year)
                        next_leap_year = current_year
                        while not self._is_leap_year(next_leap_year) or (self._is_leap_year(next_leap_year) and datetime(next_leap_year, 2, 29).date() < today.date()):
                            next_leap_year += 1
                        
                        next_feb_29 = datetime(next_leap_year, 2, 29)
                        days_until = (next_feb_29.date() - today.date()).days
                        
                        birthday_list.append({
                            'name': char_name,
                            'date_str': birthday_str,
                            'days_until': days_until,
                            'is_today': (today.month == 2 and today.day == 29 and self._is_leap_year(current_year)),
                            'month': 2,
                            'day': 29
                        })
                    else:
                        # Parse birthday to get month and day
                        birthday_date = datetime.strptime(f"{birthday_str} {current_year}", '%B %d %Y')
                        
                        # Calculate days until birthday
                        if birthday_date.date() < today.date():
                            # Birthday already passed this year, use next year
                            next_birthday = birthday_date.replace(year=current_year + 1)
                            days_until = (next_birthday.date() - today.date()).days
                        else:
                            days_until = (birthday_date.date() - today.date()).days
                        
                        birthday_list.append({
                            'name': char_name,
                            'date_str': birthday_str,
                            'days_until': days_until,
                            'is_today': days_until == 0,
                            'month': birthday_date.month,
                            'day': birthday_date.day
                        })
                    
                except ValueError as e:
                    logger.warning(f"Could not parse birthday for {char_name}: {birthday_str} - {e}")
                    continue
            
            # Sort by calendar order (month, then day)
            birthday_list.sort(key=lambda x: (x['month'], x['day']))
            
            return birthday_list
            
        except Exception as e:
            logger.error(f"Error sorting birthdays: {e}")
            return []
    
    def _is_leap_year(self, year):
        """Check if a year is a leap year"""
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    
    def _load_birthday_cache(self):
        """Load cached birthday data"""
        try:
            if os.path.exists(self.birthday_cache_file):
                with open(self.birthday_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                self.birthdays = cache_data.get('birthdays', {})
                logger.info(f"Loaded {len(self.birthdays)} birthdays from cache")
            else:
                logger.info("No birthday cache found - starting fresh")
                self.birthdays = {}
                
        except Exception as e:
            logger.error(f"Error loading birthday cache: {e}")
            self.birthdays = {}
    
    def _save_birthday_cache(self):
        """Save birthday data to cache"""
        try:
            cache_data = {
                'birthdays': self.birthdays,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.birthday_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.birthdays)} birthdays to cache")
            
        except Exception as e:
            logger.error(f"Error saving birthday cache: {e}")