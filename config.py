"""
Configuration Management
Handles environment variables and bot settings
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the Discord bot"""
    
    def __init__(self):
        # Discord Configuration
        self.DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
        self.DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
        
        # Website Configuration
        self.WEBSITE_URL = os.getenv('WEBSITE_URL', 'https://kyuukei.com/about/')
        
        # Scheduling Configuration
        self.DAILY_TIME = os.getenv('DAILY_TIME', '00:01')  # UTC time (12:01 AM EST)
        
        # Optional Configuration
        self.BOT_PREFIX = os.getenv('BOT_PREFIX', '!')
        self.MAX_IMAGE_SIZE = int(os.getenv('MAX_IMAGE_SIZE', '1024'))  # pixels
        
        # Logging Configuration
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        
    def validate(self):
        """Validate required configuration"""
        required_vars = [
            'DISCORD_TOKEN',
            'DISCORD_CHANNEL_ID',
            'WEBSITE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(self, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True
    
    def __str__(self):
        """String representation of config (without sensitive data)"""
        return f"""
Configuration:
- Website URL: {self.WEBSITE_URL}
- Channel ID: {self.DISCORD_CHANNEL_ID}
- Daily Time: {self.DAILY_TIME} UTC (12:01 AM EST)
- Bot Prefix: {self.BOT_PREFIX}
- Max Image Size: {self.MAX_IMAGE_SIZE}px
- Log Level: {self.LOG_LEVEL}
"""