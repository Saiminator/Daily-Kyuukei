"""
Task Scheduler for Daily Character Updates
Handles automated daily posting
"""

import asyncio
import logging
from datetime import datetime, time
import schedule
from config import Config

logger = logging.getLogger(__name__)

class DailyScheduler:
    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config
        self.running = False
        self.last_character = None  # Track last posted character to detect changes
        
    async def start(self):
        """Start the scheduler"""
        self.running = True
        logger.info(f"Starting scheduler - daily posts at {self.config.DAILY_TIME} UTC (12:00 AM EST)")
        
        # Schedule daily task
        schedule.every().day.at(self.config.DAILY_TIME).do(self._schedule_daily_post)

        # Schedule special non-leap-year birthday messages
        schedule.every().day.at('22:00').do(self._schedule_february_warning_post)
        schedule.every().day.at('00:05').do(self._schedule_march_erasure_post)
        
        # Run scheduler loop
        while self.running:
            try:
                # Run pending scheduled tasks
                schedule.run_pending()
                
                # Wait a bit before checking again
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def _schedule_daily_post(self):
        """Schedule a daily post (called by schedule library)"""
        try:
            # Create a task for the async function
            asyncio.create_task(self._execute_daily_post())
        except Exception as e:
            logger.error(f"Error scheduling daily post: {e}")
    

    def _schedule_february_warning_post(self):
        """Schedule Feb 28 warning message check"""
        try:
            asyncio.create_task(self._execute_february_warning_post())
        except Exception as e:
            logger.error(f"Error scheduling Feb 28 warning post: {e}")

    def _schedule_march_erasure_post(self):
        """Schedule Mar 1 erasure message check"""
        try:
            asyncio.create_task(self._execute_march_erasure_post())
        except Exception as e:
            logger.error(f"Error scheduling March erasure post: {e}")

    async def _execute_daily_post(self):
        """Execute the daily character post"""
        try:
            logger.info("Executing scheduled daily character post")
            
            # Wait for bot to be ready
            if not self.bot.is_ready():
                logger.info("Waiting for bot to be ready...")
                await self.bot.wait_until_ready()
            
            # Check if we recently posted to avoid duplicates with manual commands
            import time
            current_time = time.time()
            if hasattr(self.bot, 'last_post_time') and self.bot.last_post_time and (current_time - self.bot.last_post_time) < 300:  # 5 minutes
                logger.info("Skipping scheduled post - recent manual post detected")
                return
            
            # Post daily character
            success = await self.bot.post_daily_character()
            
            if success:
                logger.info("Daily character post completed successfully")
            else:
                logger.error("Daily character post failed")
                
        except Exception as e:
            logger.error(f"Error executing daily post: {e}")
    

    async def _execute_february_warning_post(self):
        """Execute Feb 28 10:00 PM warning message (non-leap-year only)"""
        try:
            if not self.bot.is_ready():
                await self.bot.wait_until_ready()

            await self.bot.send_february_birthday_warning_message()
        except Exception as e:
            logger.error(f"Error executing Feb 28 warning post: {e}")

    async def _execute_march_erasure_post(self):
        """Execute Mar 1 12:05 AM erasure message (when Feb 29 did not occur)"""
        try:
            if not self.bot.is_ready():
                await self.bot.wait_until_ready()

            await self.bot.send_march_first_erasure_message()
        except Exception as e:
            logger.error(f"Error executing March erasure post: {e}")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        try:
            schedule.clear()
        except Exception as e:
            logger.error(f"Error clearing schedule: {e}")
        logger.info("Scheduler stopped")
    
    async def test_immediate_post(self):
        """Test function to trigger an immediate post"""
        try:
            logger.info("Testing immediate character post")
            await self._execute_daily_post()
        except Exception as e:
            logger.error(f"Error in test post: {e}")
