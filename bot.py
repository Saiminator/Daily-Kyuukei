"""
Discord Bot Implementation
Handles Discord interactions and character posting
"""

import discord
from discord.ext import commands
import logging
import aiohttp
import asyncio
from io import BytesIO
from PIL import Image
import os
import json
from datetime import datetime
from scraper import CharacterScraper
from birthday_scraper import BirthdayScraper
from notification_manager import NotificationManager
from character_tracker import CharacterTracker
from config import Config

logger = logging.getLogger(__name__)

class CharacterBot(commands.Bot):
    def __init__(self, config: Config):
        # Configure bot intents
        intents = discord.Intents.default()
        intents.message_content = True  # Now enabled in Discord Developer Portal
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description='Daily Character of the Day Bot'
        )
        
        self.config = config
        self.scraper = CharacterScraper(config)
        self.birthday_scraper = BirthdayScraper(config)
        self.notification_manager = NotificationManager()
        self.character_tracker = CharacterTracker()
        self.last_character_data = None  # Cache for character data
        self.last_post_time = None  # Track when we last posted to prevent duplicates
        self.posting_lock = asyncio.Lock()  # Prevent concurrent posting
        self.character_cache_file = "character_cache.json"  # Persistent storage file
        
        # Load cached character data on startup
        self._load_character_cache()
        
        # Initialize birthday data and character tracker on startup
        asyncio.create_task(self._initialize_birthdays())
        asyncio.create_task(self._initialize_character_tracker())
        
        # Add commands
        self.add_commands()
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, 
                name="for character updates"
            )
        )
        
        # Check if we missed the daily update
        await self._check_missed_daily_update()
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        logger.error(f"Command error in {ctx.command}: {error}")
        await ctx.send(f"An error occurred: {str(error)}")
    
    def add_commands(self):
        """Add bot commands"""
        
        @self.command(name='character', help='Get today\'s character of the day')
        async def get_character(ctx):
            """Show cached character information without rescaping"""
            if self.last_character_data:
                # Check for fresh bread with cached data
                fresh_bread_days = None
                if self.last_character_data.get('character_today'):
                    fresh_bread_days = await self.character_tracker.check_fresh_bread(self.last_character_data['character_today'])
                
                # Check for birthdays
                birthday_characters = await self._check_today_birthdays()
                
                await self.post_character_update(ctx.channel, self.last_character_data, birthday_characters, fresh_bread_days)
            else:
                await ctx.send("❌ No character data available. Use `!update` to fetch latest character information.")
        
        @self.command(name='birthdays', help='Show upcoming character birthdays')
        async def birthdays_command(ctx):
            """Show sorted list of character birthdays"""
            try:
                # Get fresh birthday data
                await self.birthday_scraper.get_character_birthdays()
                sorted_birthdays = self.birthday_scraper.get_sorted_birthdays()
                
                if not sorted_birthdays:
                    await ctx.send("📅 No birthday information available yet. The bot is still collecting character data.")
                    return
                
                # Get character URL mapping from characters.json
                characters_data = await self.birthday_scraper.get_character_list()
                char_url_map = {}
                if characters_data:
                    for char in characters_data:
                        char_name = char.get('title', '')
                        char_url = char.get('url', '')
                        if char_name and char_url:
                            char_url_map[char_name] = f"https://kyuukei.com{char_url}"
                
                # Create embed with birthday list
                embed = discord.Embed(
                    title="🎂 Character Birthdays",
                    description="Character birthdays in calendar order",
                    color=0xffd700
                )
                
                # Get current date for "Today" line
                from datetime import datetime
                today = datetime.now()
                today_str = today.strftime('%B %d')
                today_month = today.month
                today_day = today.day
                
                birthday_lines = []
                today_line_added = False
                
                for birthday in sorted_birthdays:
                    char_name = birthday['name']
                    date_str = birthday['date_str']
                    days_until = birthday['days_until']
                    is_today = birthday['is_today']
                    birth_month = birthday['month']
                    birth_day = birthday['day']
                    
                    # Add "Today" line at the right chronological position
                    if not today_line_added and (
                        (birth_month > today_month) or 
                        (birth_month == today_month and birth_day > today_day)
                    ):
                        birthday_lines.append(f"**Today ({today_str})**")
                        today_line_added = True
                    
                    # Add birthday line with correct hyperlink
                    char_url = char_url_map.get(char_name, f"https://kyuukei.com/characters/{char_name}/")
                    if is_today:
                        line = f"**[{char_name}]({char_url}) {date_str} (Today!)**"
                    else:
                        line = f"[{char_name}]({char_url}) {date_str} ({days_until} days)"
                    
                    birthday_lines.append(line)
                
                # If we went through all birthdays and today is after all of them, add at end
                if not today_line_added:
                    birthday_lines.append(f"**Today ({today_str})**")
                
                # Split into chunks if too long
                if len(birthday_lines) > 25:
                    birthday_text = "\n".join(birthday_lines[:25]) + "\n\n... and more!"
                else:
                    birthday_text = "\n".join(birthday_lines)
                
                embed.description = birthday_text
                embed.set_footer(text=f"Total characters: {len(sorted_birthdays)} • Calendar year order")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in birthdays command: {e}")
                await ctx.send("❌ Error fetching birthday information. Please try again later.")
        
        @self.command(name='bread', help='Show character of the day statistics (!bread "week, month, year")')
        async def bread_command(ctx, timeframe: str = 'all'):
            """Show character of the day statistics with optional time frame"""
            try:
                # Validate timeframe
                valid_timeframes = ['all', 'week', 'month', 'year']
                if timeframe.lower() not in valid_timeframes:
                    await ctx.send(f"❌ Invalid timeframe. Use: {', '.join(valid_timeframes)}")
                    return
                
                timeframe = timeframe.lower()
                
                # Get character statistics
                stats = await self.character_tracker.get_character_stats(timeframe)
                
                if not stats:
                    time_desc = {
                        'all': 'all time',
                        'week': 'the last 7 days', 
                        'month': 'the last 30 days',
                        'year': 'the last year'
                    }[timeframe]
                    await ctx.send(f"📊 No character data available for {time_desc}.")
                    return
                
                # Format and send the message
                formatted_message = await self.character_tracker.format_bread_message(stats, timeframe)
                
                # Split message if too long for Discord
                if len(formatted_message) > 2000:
                    lines = formatted_message.split('\n')
                    current_message = lines[0] + '\n' + lines[1] + '\n'  # Header
                    
                    for line in lines[2:]:
                        if len(current_message + line + '\n') > 1900:
                            await ctx.send(f"```\n{current_message}```")
                            current_message = line + '\n'
                        else:
                            current_message += line + '\n'
                    
                    if current_message.strip():
                        await ctx.send(f"```\n{current_message}```")
                else:
                    await ctx.send(f"```\n{formatted_message}```")
                
            except Exception as e:
                logger.error(f"Error in bread command: {e}")
                await ctx.send("❌ Error fetching character statistics. Please try again later.")
        
        @self.command(name='notifyme', help='Subscribe to daily character and birthday notifications')
        async def notifyme_command(ctx):
            """Subscribe user to daily notifications"""
            user_id = ctx.author.id
            
            if self.notification_manager.is_subscribed(user_id):
                await ctx.send("✅ You are already subscribed to daily notifications!")
                return
            
            success = self.notification_manager.add_subscriber(user_id)
            if success:
                subscriber_count = self.notification_manager.get_subscriber_count()
                await ctx.send(f"🔔 You have been subscribed to daily character and birthday notifications!\n**Total subscribers:** {subscriber_count}\n\nYou will receive DMs when new daily characters and birthdays are posted. Use `!unnotifyme` to unsubscribe.")
            else:
                await ctx.send("❌ Failed to subscribe you to notifications. Please try again.")
        
        @self.command(name='unnotifyme', help='Unsubscribe from daily character and birthday notifications')
        async def unnotifyme_command(ctx):
            """Unsubscribe user from daily notifications"""
            user_id = ctx.author.id
            
            if not self.notification_manager.is_subscribed(user_id):
                await ctx.send("ℹ️ You are not currently subscribed to notifications.")
                return
            
            success = self.notification_manager.remove_subscriber(user_id)
            if success:
                subscriber_count = self.notification_manager.get_subscriber_count()
                await ctx.send(f"🔕 You have been unsubscribed from daily notifications.\n**Remaining subscribers:** {subscriber_count}\n\nYou will no longer receive DMs about daily characters and birthdays.")
            else:
                await ctx.send("❌ Failed to unsubscribe you from notifications. Please try again.")
        
        @self.command(name='pushdm', help='Pushes daily notifications to subscribers (owner only)')
        async def pushdm_command(ctx):
            """Manually send daily notifications to all subscribers - restricted to owner"""
            logger.info(f"PushDM command called by {ctx.author.id} ({ctx.author.name})")
            
            # Check if user is authorized (your Discord user ID)
            if ctx.author.id != 308154672143794176:
                await ctx.send("❌ This command is restricted to the bot owner.")
                return
            
            if not self.last_character_data:
                await ctx.send("❌ No character data available. Use `!update` first to get today's character.")
                return
            
            try:
                # Check for fresh bread
                fresh_bread_days = None
                if self.last_character_data.get('character_today'):
                    fresh_bread_days = await self.character_tracker.check_fresh_bread(self.last_character_data['character_today'])
                
                # Check for birthdays
                birthday_characters = await self._check_today_birthdays()
                
                # Send notifications to subscribers
                await self.notification_manager.send_daily_notifications(self, self.last_character_data, birthday_characters, fresh_bread_days)
                
                subscriber_count = self.notification_manager.get_subscriber_count()
                await ctx.send(f"✅ Daily notifications sent to {subscriber_count} subscriber(s)!")
                
            except Exception as e:
                logger.error(f"Error in pushdm command: {e}")
                await ctx.send(f"❌ Error sending notifications: {str(e)}")
        
        @self.command(name='update', help='Post character update to the main channel (owner only)')
        async def update_command(ctx):
            """Post current character update to the configured channel - restricted to owner"""
            logger.info(f"Update command called by {ctx.author.id} ({ctx.author.name})")
            
            # Check if user is authorized (your Discord user ID)
            if ctx.author.id != 308154672143794176:
                await ctx.send("❌ This command is restricted to the bot owner.")
                return
            
            # Time restriction removed per user request
            
            try:
                # Only send one response - either success or failure
                success = await self.post_daily_character(send_notifications=False)  # Don't send DMs from manual update
                if success:
                    await ctx.send("✅ Character posted to main channel!")
                else:
                    await ctx.send("❌ Failed to post character update.")
            except Exception as e:
                logger.error(f"Error in update command: {e}")
                await ctx.send(f"❌ Error: {str(e)}")
    
    async def post_daily_character(self, send_notifications=True):
        """Post daily character update to the configured channel"""
        async with self.posting_lock:  # Prevent concurrent posting
            try:
                # Time restriction removed per user request
                import time
                current_time = time.time()
                
                channel_id = self.config.DISCORD_CHANNEL_ID
                if not channel_id:
                    logger.error("DISCORD_CHANNEL_ID not configured")
                    return False
                    
                channel = self.get_channel(int(channel_id))
                if not channel:
                    logger.error(f"Could not find channel with ID: {channel_id}")
                    return False
                
                # Check if channel is a text channel that supports sending messages
                if not isinstance(channel, (discord.TextChannel, discord.DMChannel, discord.GroupChannel)):
                    logger.error(f"Channel {channel_id} is not a text channel (type: {type(channel).__name__})")
                    return False
                
                logger.info("Starting daily character scraping...")
                result = await self.scraper.scrape_character_data(self.character_tracker)
                
                if result:
                    # Cache the result for the character command
                    self.last_character_data = result
                    self._save_character_cache(result)  # Save to persistent storage
                    
                    # Check for fresh bread before logging today's character
                    fresh_bread_days = None
                    if result.get('character_today'):
                        fresh_bread_days = await self.character_tracker.check_fresh_bread(result['character_today'])
                        
                        # Log character of the day for bread tracking
                        await self.character_tracker.log_character_of_day(
                            result['character_today'], 
                            result.get('date')
                        )
                    
                    # Check for birthdays
                    birthday_characters = await self._check_today_birthdays()
                    
                    logger.info(f"About to call post_character_update from post_daily_character for channel {channel.id}")
                    await self.post_character_update(channel, result, birthday_characters, fresh_bread_days)
                    
                    # Send notifications to subscribers only if requested (scheduled posts, not manual updates)
                    if send_notifications:
                        await self.notification_manager.send_daily_notifications(self, result, birthday_characters, fresh_bread_days)
                    
                    self.last_post_time = current_time  # Update last post time
                    return True
                else:
                    try:
                        await channel.send("❌ Failed to fetch today's character information. Please check the website.")
                    except Exception as send_error:
                        logger.error(f"Failed to send error message: {send_error}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error posting daily character: {e}")
                return False
    
    async def post_character_update(self, channel, character_data, birthday_characters=None, fresh_bread_days=None):
        """Post character update with embed and image"""
        try:
            logger.info(f"post_character_update called for channel: {channel.id if hasattr(channel, 'id') else 'unknown'}")
            # Create embed
            embed = discord.Embed(
                title="🎭 Character of the Day",
                description=f"**Date:** {character_data.get('date', 'Unknown')}",
                color=0xff6b6b
            )
            
            # Add character information with hyperlinks
            if character_data.get('character_today'):
                character_name = character_data['character_today']
                character_link = self._get_character_url(character_name)
                if character_link:
                    character_value = f"[{character_name}]({character_link})"
                else:
                    character_value = character_name
                
                embed.add_field(
                    name="Today's Character",
                    value=character_value,
                    inline=False
                )
            
            if character_data.get('character_yesterday'):
                character_name = character_data['character_yesterday']
                character_link = self._get_character_url(character_name)
                if character_link:
                    character_value = f"[{character_name}]({character_link})"
                else:
                    character_value = character_name
                
                embed.add_field(
                    name="Yesterday's Character",
                    value=character_value,
                    inline=False
                )
            
            # Add birthday information if any
            if birthday_characters:
                birthday_text = "🎉 " + ", ".join(birthday_characters)
                embed.add_field(
                    name="Birthday Today!",
                    value=birthday_text,
                    inline=False
                )
            
            embed.set_footer(text="Daily Character Bot • Updated automatically")
            
            # Handle image
            file_to_send = None
            if character_data.get('image_url'):
                try:
                    image_file = await self.download_image(character_data['image_url'])
                    if image_file:
                        file_to_send = discord.File(image_file, filename="character.png")
                        embed.set_image(url="attachment://character.png")
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
            
            # Send message
            if file_to_send:
                await channel.send(embed=embed, file=file_to_send)
            else:
                await channel.send(embed=embed)
            
            # Post fresh bread message if applicable
            if fresh_bread_days is not None and character_data.get('character_today'):
                await self._post_fresh_bread_message(channel, character_data['character_today'], fresh_bread_days)
            
            # Post birthday images if there are birthdays today
            if birthday_characters:
                await self._post_birthday_images(channel, birthday_characters)
            
            logger.info("Successfully posted character update")
            
        except Exception as e:
            logger.error(f"Error posting character update: {e}")
            try:
                await channel.send(f"❌ Error posting character update: {str(e)}")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
    
    def _save_character_cache(self, character_data):
        """Save character data to persistent storage"""
        try:
            cache_data = {
                "character_data": character_data,
                "timestamp": datetime.now().isoformat(),
                "last_post_time": self.last_post_time
            }
            with open(self.character_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Character data saved to {self.character_cache_file}")
        except Exception as e:
            logger.error(f"Error saving character cache: {e}")
    
    def _load_character_cache(self):
        """Load character data from persistent storage"""
        try:
            if os.path.exists(self.character_cache_file):
                with open(self.character_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                self.last_character_data = cache_data.get("character_data")
                self.last_post_time = cache_data.get("last_post_time")
                
                # Log what was loaded
                if self.last_character_data:
                    char_name = self.last_character_data.get('character_today', 'Unknown')
                    date = self.last_character_data.get('date', 'Unknown')
                    logger.info(f"Loaded cached character: {char_name} for {date}")
                else:
                    logger.info("No character data found in cache")
            else:
                logger.info("No character cache file found - starting fresh")
        except Exception as e:
            logger.error(f"Error loading character cache: {e}")
            self.last_character_data = None
            self.last_post_time = None
    
    async def _initialize_birthdays(self):
        """Initialize birthday data on bot startup"""
        try:
            await asyncio.sleep(5)  # Wait for bot to fully initialize
            logger.info("Initializing birthday data...")
            birthdays = await self.birthday_scraper.get_character_birthdays()
            logger.info(f"Loaded birthday data for {len(birthdays)} characters")
        except Exception as e:
            logger.error(f"Error initializing birthdays: {e}")
    
    async def _initialize_character_tracker(self):
        """Initialize character tracker on bot startup"""
        try:
            await asyncio.sleep(6)  # Wait for bot to fully initialize
            logger.info("Initializing character tracker...")
            await self.character_tracker.initialize()
            logger.info("Character tracker initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing character tracker: {e}")
    
    async def _check_today_birthdays(self):
        """Check if any characters have birthdays today"""
        try:
            # Refresh birthday data
            await self.birthday_scraper.get_character_birthdays()
            # Get today's birthday characters
            birthday_characters = self.birthday_scraper.get_today_birthdays()
            
            if birthday_characters:
                logger.info(f"Today's birthdays: {', '.join(birthday_characters)}")
            
            return birthday_characters
            
        except Exception as e:
            logger.error(f"Error checking today's birthdays: {e}")
            return []
    
    async def _post_fresh_bread_message(self, channel, character_name, fresh_bread_result):
        """Post fresh bread message for a character returning after being away or appearing for the first time"""
        try:
            if fresh_bread_result == "debut":
                # Character has never appeared before
                embed = discord.Embed(
                    title="🍞✨ Fresh from the Oven!",
                    description=f"Never before seen, fresh from the oven... **{character_name}** is here!",
                    color=0xffd700  # Gold color for debut
                )
                logger.info(f"Posted debut message for {character_name}")
            else:
                # Character is returning after being away
                embed = discord.Embed(
                    title="🍞➜✨ Fresh Bread!",
                    description=f"Time passes… bread freshens. **{character_name}** returns after **{fresh_bread_result}** days.",
                    color=0xffa500  # Orange color for returning bread
                )
                logger.info(f"Posted fresh bread message for {character_name} after {fresh_bread_result} days")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error posting fresh bread message: {e}")

    async def _post_birthday_images(self, channel, birthday_characters):
        """Post birthday images for characters celebrating today"""
        try:
            for char_name in birthday_characters:
                # Get character's birthday image URL
                first_name = char_name.split()[0].lower()
                birthday_image_url = f"https://kyuukei.s3.us-east-2.amazonaws.com/character/{first_name}/pfp.png"
                
                # Create birthday embed with hyperlinked character name
                character_link = self._get_character_url(char_name)
                if character_link:
                    char_display = f"[{char_name}]({character_link})"
                else:
                    char_display = char_name
                
                embed = discord.Embed(
                    title="🎉 Happy Birthday!",
                    description=f"**{char_display}** is celebrating their birthday today!",
                    color=0xffd700
                )
                
                # Try to add birthday image
                file_to_send = None
                try:
                    image_file = await self.download_image(birthday_image_url)
                    if image_file:
                        file_to_send = discord.File(image_file, filename=f"{char_name.replace(' ', '_')}_birthday.png")
                        embed.set_image(url=f"attachment://{char_name.replace(' ', '_')}_birthday.png")
                except Exception as e:
                    logger.error(f"Error processing birthday image for {char_name}: {e}")
                
                embed.set_footer(text="🎂 Happy Birthday! • Character Birthday Bot")
                
                # Send birthday message
                if file_to_send:
                    await channel.send(embed=embed, file=file_to_send)
                else:
                    await channel.send(embed=embed)
                
                logger.info(f"Posted birthday message for {char_name}")
                
        except Exception as e:
            logger.error(f"Error posting birthday images: {e}")
    
    async def _check_missed_daily_update(self):
        """Check if we missed the daily update and catch up if needed"""
        try:
            from datetime import datetime, timedelta
            
            current_time = datetime.now()
            current_date_str = current_time.strftime('%B %d, %Y')
            
            # Check if we have cached data and if it's for today
            if self.last_character_data:
                cached_date = self.last_character_data.get('date', '')
                
                if cached_date == current_date_str:
                    logger.info(f"Character data is current for {current_date_str}")
                    return
                else:
                    logger.info(f"Cached data is outdated (cached: {cached_date}, current: {current_date_str})")
            else:
                logger.info("No cached character data found")
            
            # If bot restarted after midnight but before scraping, post today's character
            logger.info("Checking if daily update was missed...")
            
            # Try to get fresh character data
            await asyncio.sleep(2)  # Give bot time to fully initialize
            result = await self.scraper.scrape_character_data()
            
            if result and result.get('date') == current_date_str:
                # Only post if it's actually new data for today
                if not self.last_character_data or self.last_character_data.get('date') != current_date_str:
                    logger.info("Missed daily update detected - posting catch-up update")
                    
                    channel_id = self.config.DISCORD_CHANNEL_ID
                    if channel_id:
                        channel = self.get_channel(int(channel_id))
                        if channel and isinstance(channel, (discord.TextChannel, discord.DMChannel, discord.GroupChannel)):
                            self.last_character_data = result
                            self._save_character_cache(result)
                            
                            # Check for birthdays on catch-up post
                            birthday_characters = await self._check_today_birthdays()
                            
                            await self.post_character_update(channel, result, birthday_characters)
                            
                            # Send notifications for catch-up post
                            await self.notification_manager.send_daily_notifications(self, result, birthday_characters)
                            
                            # Update post time to prevent scheduler conflicts
                            import time
                            self.last_post_time = time.time()
                            
                            logger.info("Catch-up post completed successfully")
                        else:
                            logger.error("Could not find valid channel for catch-up post")
                    else:
                        logger.error("No channel ID configured for catch-up post")
                else:
                    logger.info("Character data is already current - no catch-up needed")
            else:
                logger.info("Could not fetch current character data for catch-up")
                
        except Exception as e:
            logger.error(f"Error checking for missed daily update: {e}")
    
    async def download_image(self, image_url):
        """Download and process image"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # Process image with PIL
                        image = Image.open(BytesIO(image_data))
                        
                        # Resize if too large (Discord limit is 8MB, but let's be conservative)
                        if image.size[0] > 1024 or image.size[1] > 1024:
                            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                        
                        # Convert to RGB if necessary
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        
                        # Save to BytesIO
                        output = BytesIO()
                        image.save(output, format='PNG', optimize=True)
                        output.seek(0)
                        
                        return output
                    else:
                        logger.error(f"Failed to download image: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    def _get_character_url(self, character_name):
        """Get character page URL from character name"""
        try:
            if not character_name or character_name in ["Character not found", "Yesterday's character not found"]:
                return None
            
            # Known character mappings
            character_urls = {
                "Hotaru Stürzen": "https://kyuukei.com/characters/Hotaru/",
                "Hotaru": "https://kyuukei.com/characters/Hotaru/",
                "Duran": "https://kyuukei.com/characters/Duran/",
                "Ibuki Weitschall": "https://kyuukei.com/characters/Ibuki/",
                "Ibuki": "https://kyuukei.com/characters/Ibuki/",
                "Emiko Stürzen": "https://kyuukei.com/characters/Emiko/",
                "Emiko": "https://kyuukei.com/characters/Emiko/",
            }
            
            # Check for exact match first
            if character_name in character_urls:
                return character_urls[character_name]
            
            # Try to construct URL from name
            # Convert "Hotaru Stürzen" -> "Hotaru"
            first_name = character_name.split()[0]
            if first_name in character_urls:
                return character_urls[first_name]
            
            # Fallback: construct URL from first name
            if first_name and len(first_name) > 1:
                return f"https://kyuukei.com/characters/{first_name}/"
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting character URL: {e}")
            return None
