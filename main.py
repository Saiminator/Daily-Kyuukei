#!/usr/bin/env python3
"""
Discord Bot for Daily Character of the Day
Main entry point for the application
"""

import asyncio
import logging
import sys
from bot import CharacterBot
from scheduler import DailyScheduler
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function to start the bot and scheduler"""
    scheduler_task = None
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            # Initialize configuration
            config = Config()
            
            # Validate required configuration
            if not config.DISCORD_TOKEN:
                logger.error("DISCORD_TOKEN is not set in environment variables")
                sys.exit(1)
                
            if not config.WEBSITE_URL:
                logger.error("WEBSITE_URL is not set in environment variables")
                sys.exit(1)
                
            if not config.DISCORD_CHANNEL_ID:
                logger.error("DISCORD_CHANNEL_ID is not set in environment variables")
                sys.exit(1)
            

            
            # Initialize bot
            bot = CharacterBot(config)
            
            # Initialize scheduler
            scheduler = DailyScheduler(bot, config)
            
            # Start scheduler in background
            scheduler_task = asyncio.create_task(scheduler.start())
            
            logger.info("Starting Discord bot...")
            
            # Start bot (this will block until the bot is stopped)
            await bot.start(config.DISCORD_TOKEN)
            break  # If we reach here, bot shut down cleanly
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            retry_count += 1
            logger.error(f"Fatal error (attempt {retry_count}/{max_retries}): {e}")
            
            if scheduler_task:
                scheduler_task.cancel()
                scheduler_task = None
            
            if retry_count < max_retries:
                wait_time = min(30 * retry_count, 300)  # Exponential backoff, max 5 minutes
                logger.info(f"Restarting in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Max retries exceeded. Exiting.")
                sys.exit(1)
        finally:
            if scheduler_task:
                scheduler_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())