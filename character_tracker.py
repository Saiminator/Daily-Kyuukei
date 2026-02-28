"""
Character Tracker for Discord Bot
Tracks character of the day statistics and provides bread command functionality
"""

import logging
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class CharacterTracker:
    def __init__(self):
        self.character_log_file = "character_daily_log.json"
        self.character_data = {}
        
    async def initialize(self):
        """Initialize character tracker - load existing data"""
        try:
            self._load_character_data()
            logger.info("Character tracker initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing character tracker: {e}")
            raise
    
    def _load_character_data(self):
        """Load character data from JSON file"""
        try:
            if os.path.exists(self.character_log_file):
                with open(self.character_log_file, 'r', encoding='utf-8') as f:
                    self.character_data = json.load(f)
                logger.info(f"Loaded character data with {len(self.character_data)} entries")
            else:
                logger.info("No character log file found - starting fresh")
                self.character_data = {}
        except Exception as e:
            logger.error(f"Error loading character data: {e}")
            self.character_data = {}
    
    def _save_character_data(self):
        """Save character data to JSON file"""
        try:
            with open(self.character_log_file, 'w', encoding='utf-8') as f:
                json.dump(self.character_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved character data with {len(self.character_data)} entries")
        except Exception as e:
            logger.error(f"Error saving character data: {e}")
    
    async def log_character_of_day(self, character_name, date_str=None):
        """Log a character as character of the day (prevents duplicates per date)"""
        try:
            # Parse date or use today
            if date_str:
                # Handle format like "July 31, 2025"
                try:
                    log_date = datetime.strptime(date_str, '%B %d, %Y').date().isoformat()
                except ValueError:
                    # Try other formats if needed
                    log_date = datetime.now().date().isoformat()
            else:
                log_date = datetime.now().date().isoformat()
            
            # Only add if not already logged for this date (one character per day)
            if log_date not in self.character_data:
                self.character_data[log_date] = character_name
                self._save_character_data()
                logger.info(f"Logged character of day: {character_name} for {log_date}")
            else:
                logger.debug(f"Date {log_date} already has character: {self.character_data[log_date]}")
                
        except Exception as e:
            logger.error(f"Error logging character of day: {e}")
    
    def _normalize_date_string(self, date_str):
        """Normalize date string to standard ISO format (YYYY-MM-DD)"""
        try:
            parts = date_str.split('-')
            if len(parts) == 3:
                year = parts[0]
                month = parts[1].zfill(2)  # Pad with leading zero if needed
                day = parts[2].zfill(2)    # Pad with leading zero if needed
                return f"{year}-{month}-{day}"
            else:
                return date_str  # Return as-is if format is unexpected
        except Exception:
            return date_str  # Return as-is if parsing fails
    
    async def get_character_stats(self, time_frame='all', year=None):
        """Get character statistics for the specified time frame"""
        try:
            # Calculate date cutoff based on time frame
            today = datetime.now().date()
            if time_frame == 'week':
                cutoff_date = today - timedelta(days=6)  # Last 7 days including today
            elif time_frame == 'month':
                cutoff_date = today - timedelta(days=29)  # Last 30 days including today
            elif time_frame == 'year':
                # Optional specific-year mode (e.g., !bread year 2025)
                if year is not None:
                    cutoff_date = None
                else:
                    cutoff_date = today - timedelta(days=364)  # Last 365 days including today
            else:  # 'all'
                cutoff_date = datetime(2000, 1, 1).date()  # Far in the past
            
            # Process character data
            character_stats = {}
            
            for log_date, char_name in self.character_data.items():
                # Normalize date format to handle missing leading zeros
                normalized_date = self._normalize_date_string(log_date)
                entry_date = datetime.fromisoformat(normalized_date).date()
                
                # Skip entries outside time frame
                if time_frame == 'year' and year is not None:
                    if entry_date.year != year:
                        continue
                elif entry_date < cutoff_date:
                    continue
                
                # Initialize character entry if not exists
                if char_name not in character_stats:
                    character_stats[char_name] = {'times_featured': 0, 'last_featured_date': None}
                
                character_stats[char_name]['times_featured'] += 1
                
                # Track most recent date
                if (character_stats[char_name]['last_featured_date'] is None or 
                    entry_date > character_stats[char_name]['last_featured_date']):
                    character_stats[char_name]['last_featured_date'] = entry_date
            
            # Convert to list format and calculate days since last
            stats = []
            for char_name, data in character_stats.items():
                last_date = data['last_featured_date']
                if last_date is not None:
                    days_since_last = (today - last_date).days
                else:
                    days_since_last = 0  # Should not happen due to data structure, but handle it
                
                stats.append({
                    'character_name': char_name,
                    'times_featured': data['times_featured'],
                    'last_featured_date': last_date,
                    'days_since_last': days_since_last
                })
            
            # Sort by times featured (desc), then by most recent date (desc)
            stats.sort(key=lambda x: (-x['times_featured'], -x['days_since_last']))
            
            return stats
                
        except Exception as e:
            logger.error(f"Error getting character stats: {e}")
            return []
    
    async def format_bread_message(self, stats, time_frame='all', year=None):
        """Format the bread command output with proper alignment"""
        if not stats:
            if time_frame == 'year' and year is not None:
                return f"📊 No character data available for year {year}."
            return f"📊 No character data available for {time_frame} timeframe."
        
        # Time frame headers
        time_headers = {
            'all': '📊 Character of the Day Stats (All-Time)',
            'week': '📊 Character of the Day Stats (Last 7 Days)',
            'month': '📊 Character of the Day Stats (Last 30 Days)', 
            'year': '📊 Character of the Day Stats (Last Year)'
        }
        
        if time_frame == 'year' and year is not None:
            header = f'📊 Character of the Day Stats ({year})'
        else:
            header = time_headers.get(time_frame, '📊 Character of the Day Stats')
        
        # Calculate max widths for alignment
        max_name_width = max(len(stat['character_name']) for stat in stats)
        max_times_width = max(len(str(stat['times_featured'])) for stat in stats)
        
        # Calculate max widths for medal winners (top 3) and regular entries separately
        medal_stats = stats[:3] if len(stats) >= 3 else stats
        regular_stats = stats[3:] if len(stats) > 3 else []
        
        max_medal_name_width = max(len(stat['character_name']) for stat in medal_stats) if medal_stats else 0
        max_regular_name_width = max(len(stat['character_name']) for stat in regular_stats) if regular_stats else 0
        
        # Build formatted lines
        lines = [header, ""]
        
        # Process top 3 (medal winners) separately from the rest
        medal_lines = []
        regular_lines = []
        
        for i, stat in enumerate(stats):
            name = stat['character_name']
            times = stat['times_featured']
            days_since = stat['days_since_last']
            
            # Add bread emoji if >30 days
            bread_emoji = " 🍞" if days_since > 30 else ""
            
            # Format days since text
            if days_since == 0:
                days_text = "today"
            elif days_since == 1:
                days_text = "1 day ago"
            else:
                days_text = f"{days_since} days ago"
            
            times_padded = str(times).rjust(max_times_width)
            
            if i == 0:
                name_padded = name.ljust(max_medal_name_width)
                line = f"🥇{name_padded} – {times_padded}x | Last featured: {days_text}{bread_emoji}"
                medal_lines.append(line)
            elif i == 1:
                name_padded = name.ljust(max_medal_name_width)
                line = f"🥈{name_padded} – {times_padded}x | Last featured: {days_text}{bread_emoji}"
                medal_lines.append(line)
            elif i == 2:
                name_padded = name.ljust(max_medal_name_width)
                line = f"🥉{name_padded} – {times_padded}x | Last featured: {days_text}{bread_emoji}"
                medal_lines.append(line)
            else:
                # Regular entries with consistent padding
                name_padded = name.ljust(max_regular_name_width)
                line = f"{name_padded} – {times_padded}x | Last featured: {days_text}{bread_emoji}"
                regular_lines.append(line)
        
        # Add medal winners
        lines.extend(medal_lines)
        
        # Add separator if there are both medal winners and regular entries
        if medal_lines and regular_lines:
            lines.append("")  # Empty line for spacing
            lines.append("─" * 50)  # Separator line
            lines.append("")  # Empty line for spacing
        
        # Add regular entries
        lines.extend(regular_lines)
        
        return "\n".join(lines)
    
    async def check_fresh_bread(self, character_name):
        """Check if a character is returning as fresh bread after being away"""
        try:
            # Find the most recent date this character was featured (excluding today)
            today = datetime.now().date()
            today_str = today.isoformat()
            last_featured_date = None
            
            for log_date, logged_char in self.character_data.items():
                if logged_char == character_name:
                    # Normalize date format
                    normalized_date = self._normalize_date_string(log_date)
                    entry_date = datetime.fromisoformat(normalized_date).date()
                    
                    # Skip today's entry to avoid interference with fresh bread detection
                    if entry_date >= today:
                        continue
                    
                    if last_featured_date is None or entry_date > last_featured_date:
                        last_featured_date = entry_date
            
            if last_featured_date is None:
                # Character has never been featured before (excluding today)
                return "debut"
            
            # Calculate days since last featured (before today)
            days_since_last = (today - last_featured_date).days
            
            # Only consider it "fresh bread" if it's been more than 30 days
            if days_since_last > 30:
                return days_since_last
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error checking fresh bread for {character_name}: {e}")
            return None

    async def close(self):
        """Close character tracker (save any pending data)"""
        try:
            self._save_character_data()
        except Exception as e:
            logger.error(f"Error closing character tracker: {e}")
