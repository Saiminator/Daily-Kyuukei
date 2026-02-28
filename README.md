Discord Character Bot
A Discord bot that automatically posts daily "Character of the Day" content by scraping character information from kyuukei.com. The bot dynamically calculates daily characters, schedules automated posts at midnight EST, and responds to manual commands.

Features
Daily Automated Posts: Schedules character updates at midnight EST (05:01 UTC)
Dynamic Character Calculation: Matches the website's exact algorithm for daily character selection
Manual Commands:
!update (owner only) - Posts current character to main channel
!character - Shows cached character data
Persistent Storage: Maintains character data across bot restarts
Crash Recovery: Automatic retry logic and missed update detection
Image Processing: Downloads and processes character images
Setup Instructions
For Raspberry Pi Hosting
Clone the repository:

git clone <repository-url>
cd discord-character-bot
Run the setup script:

chmod +x install_dependencies.sh
./install_dependencies.sh
Configure environment variables:

cp .env.example .env
nano .env  # Fill in your Discord token and channel ID
Start the bot:

source bot_env/bin/activate
python3 run_bot.py
Configuration
Create a .env file with the following variables:

DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
WEBSITE_URL=https://kyuukei.com/about/
DAILY_TIME=05:01
BOT_PREFIX=!
Required Dependencies
Python 3.7+
discord.py
requests
beautifulsoup4
schedule
python-dotenv
Pillow
aiohttp
pytz
Architecture
The bot follows a modular architecture:

main.py - Application entry point with retry logic
bot.py - Discord bot implementation and command handling
scheduler.py - Daily posting automation
scraper.py - Website scraping and character calculation
config.py - Environment variable management
How It Works
The bot scrapes character data from kyuukei.com/characters.json
Uses the same hash algorithm as the website to calculate daily characters
Schedules automatic posts at midnight EST
Maintains persistent storage to survive restarts
Provides manual commands for immediate posting
License
This project is for personal use and educational purposes.