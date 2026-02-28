"""
Notification Manager for Discord Bot
Handles user notification subscriptions and DM sending
"""

import json
import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        self.notification_file = "notifications.json"
        self.subscribers = []
        self.message_queue = []
        self.is_processing_queue = False
        self._load_subscribers()
    
    def add_subscriber(self, user_id):
        """Add a user to the notification list"""
        try:
            user_id = int(user_id)
            if user_id not in self.subscribers:
                self.subscribers.append(user_id)
                self._save_subscribers()
                logger.info(f"Added user {user_id} to notification list")
                return True
            return False  # Already subscribed
            
        except Exception as e:
            logger.error(f"Error adding subscriber {user_id}: {e}")
            return False
    
    def remove_subscriber(self, user_id):
        """Remove a user from the notification list"""
        try:
            user_id = int(user_id)
            if user_id in self.subscribers:
                self.subscribers.remove(user_id)
                self._save_subscribers()
                logger.info(f"Removed user {user_id} from notification list")
                return True
            return False  # Not subscribed
            
        except Exception as e:
            logger.error(f"Error removing subscriber {user_id}: {e}")
            return False
    
    def is_subscribed(self, user_id):
        """Check if a user is subscribed to notifications"""
        try:
            return int(user_id) in self.subscribers
        except:
            return False
    
    def get_subscriber_count(self):
        """Get the number of subscribers"""
        return len(self.subscribers)
    
    def get_subscribers(self):
        """Get list of all subscribers"""
        return self.subscribers.copy()
    
    async def send_daily_notifications(self, bot, character_data, birthday_characters=None, fresh_bread_days=None):
        """Queue daily character notifications for all subscribers - respects Discord rate limits"""
        if not self.subscribers:
            return
        
        try:
            queued_count = 0
            
            for user_id in self.subscribers:
                try:
                    user = bot.get_user(user_id)
                    if not user:
                        user = await bot.fetch_user(user_id)
                    
                    if user:
                        # Queue the message instead of sending immediately
                        await self._queue_user_notification(user, bot, character_data, birthday_characters, fresh_bread_days)
                        queued_count += 1
                    else:
                        logger.warning(f"Could not find user {user_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to queue notification for user {user_id}: {e}")
            
            logger.info(f"Queued {queued_count} notifications for rate-limited sending")
            
            # Start processing the queue if not already running
            if not self.is_processing_queue:
                asyncio.create_task(self._process_message_queue())
            
        except Exception as e:
            logger.error(f"Error queueing daily notifications: {e}")
    
    async def _queue_user_notification(self, user, bot, character_data, birthday_characters=None, fresh_bread_days=None):
        """Queue notification messages for a user to respect rate limits"""
        try:
            # Queue main character message
            main_message = {
                'type': 'character_update',
                'user': user,
                'bot': bot,
                'character_data': character_data,
                'birthday_characters': birthday_characters
            }
            self.message_queue.append(main_message)
            
            # Queue fresh bread or debut message if applicable
            if fresh_bread_days is not None and character_data.get('character_today'):
                if fresh_bread_days == "debut":
                    # Character debut message
                    debut_message = {
                        'type': 'debut',
                        'user': user,
                        'bot': bot,
                        'character_name': character_data['character_today']
                    }
                    self.message_queue.append(debut_message)
                else:
                    # Regular fresh bread message
                    fresh_bread_message = {
                        'type': 'fresh_bread',
                        'user': user,
                        'bot': bot,
                        'character_name': character_data['character_today'],
                        'days_since_last': fresh_bread_days
                    }
                    self.message_queue.append(fresh_bread_message)
            
            # Queue birthday messages separately (each birthday gets its own message)
            if birthday_characters:
                for char_name in birthday_characters:
                    birthday_message = {
                        'type': 'birthday_image',
                        'user': user,
                        'bot': bot,
                        'character_name': char_name
                    }
                    self.message_queue.append(birthday_message)
            
        except Exception as e:
            logger.error(f"Error queueing user notification: {e}")
            raise
    
    async def _process_message_queue(self):
        """Process the message queue at Discord-safe rate (1 message per second)"""
        if self.is_processing_queue:
            return
        
        self.is_processing_queue = True
        success_count = 0
        failed_count = 0
        
        try:
            logger.info(f"Starting to process {len(self.message_queue)} queued messages")
            
            while self.message_queue:
                message = self.message_queue.pop(0)
                
                try:
                    if message['type'] == 'character_update':
                        await self._send_character_update_to_user(
                            message['user'], 
                            message['bot'], 
                            message['character_data'], 
                            message['birthday_characters']
                        )
                    elif message['type'] == 'fresh_bread':
                        await self._send_fresh_bread_to_user(
                            message['user'],
                            message['bot'],
                            message['character_name'],
                            message['days_since_last']
                        )
                    elif message['type'] == 'debut':
                        await self._send_debut_to_user(
                            message['user'],
                            message['bot'],
                            message['character_name']
                        )
                    elif message['type'] == 'birthday_image':
                        await self._send_single_birthday_image_to_user(
                            message['user'],
                            message['bot'],
                            message['character_name']
                        )
                    
                    success_count += 1
                    logger.debug(f"Sent message {success_count} to user")
                    
                except Exception as e:
                    logger.error(f"Failed to send queued message: {e}")
                    failed_count += 1
                
                # Rate limit: 1 message per second for DMs
                if self.message_queue:  # Only sleep if there are more messages
                    await asyncio.sleep(1.0)
            
            logger.info(f"Finished processing message queue: {success_count} successful, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error processing message queue: {e}")
        finally:
            self.is_processing_queue = False
    
    async def _send_character_update_to_user(self, user, bot, character_data, birthday_characters=None):
        """Send the EXACT same character update as main channel to a user via DM"""
        try:
            import discord
            
            # Create embed EXACTLY like main channel
            embed = discord.Embed(
                title="🎭 Character of the Day",
                description=f"**Date:** {character_data.get('date', 'Unknown')}",
                color=0xff6b6b
            )
            
            # Add character information with hyperlinks EXACTLY like main channel
            if character_data.get('character_today'):
                character_name = character_data['character_today']
                character_link = bot._get_character_url(character_name)
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
                character_link = bot._get_character_url(character_name)
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
            
            embed.set_footer(text="Daily notifications • Type !unnotifyme to stop these messages")
            
            # Handle image EXACTLY like main channel
            file_to_send = None
            if character_data.get('image_url'):
                try:
                    image_file = await bot.download_image(character_data['image_url'])
                    if image_file:
                        file_to_send = discord.File(image_file, filename="character.png")
                        embed.set_image(url="attachment://character.png")
                except Exception as e:
                    logger.error(f"Error processing image for DM: {e}")
            
            # Send message EXACTLY like main channel
            if file_to_send:
                await user.send(embed=embed, file=file_to_send)
            else:
                await user.send(embed=embed)
            
            # Note: Birthday images are queued separately to respect rate limits
            
        except Exception as e:
            logger.error(f"Error sending character update to user: {e}")
            raise
    
    async def _send_fresh_bread_to_user(self, user, bot, character_name, days_since_last):
        """Send fresh bread message to user EXACTLY like main channel"""
        try:
            import discord
            
            # Create embed EXACTLY like main channel
            embed = discord.Embed(
                title="🍞➜✨ Fresh Bread!",
                description=f"Time passes… bread freshens. **{character_name}** returns after **{days_since_last}** days.",
                color=0xffa500  # Orange color for bread
            )
            
            embed.set_footer(text="Daily notifications • Type !unnotifyme to stop these messages")
            
            # Send message
            await user.send(embed=embed)
            logger.info(f"Sent fresh bread DM for {character_name} after {days_since_last} days to user")
            
        except Exception as e:
            logger.error(f"Error sending fresh bread message to user: {e}")
            raise

    async def _send_debut_to_user(self, user, bot, character_name):
        """Send debut message to user EXACTLY like main channel"""
        try:
            import discord
            
            # Create embed EXACTLY like main channel
            embed = discord.Embed(
                title="🍞✨ Fresh from the Oven!",
                description=f"Never before seen, fresh from the oven... **{character_name}** is here!",
                color=0xffd700  # Gold color for debut
            )
            
            embed.set_footer(text="Daily notifications • Type !unnotifyme to stop these messages")
            
            # Send message
            await user.send(embed=embed)
            logger.info(f"Sent debut DM for {character_name} to user")
            
        except Exception as e:
            logger.error(f"Error sending debut message to user: {e}")
            raise
    
    async def _send_single_birthday_image_to_user(self, user, bot, char_name):
        """Send a single birthday image to user EXACTLY like main channel (called from queue)"""
        try:
            import discord
            
            # Get character's birthday image URL EXACTLY like main channel
            first_name = char_name.split()[0].lower()
            birthday_image_url = f"https://kyuukei.s3.us-east-2.amazonaws.com/character/{first_name}/pfp.png"
            
            # Create birthday embed with hyperlinked character name EXACTLY like main channel
            character_link = bot._get_character_url(char_name)
            if character_link:
                char_display = f"[{char_name}]({character_link})"
            else:
                char_display = char_name
            
            embed = discord.Embed(
                title="🎉 Happy Birthday!",
                description=f"**{char_display}** is celebrating their birthday today!",
                color=0xffd700
            )
            
            # Try to add birthday image EXACTLY like main channel
            file_to_send = None
            try:
                image_file = await bot.download_image(birthday_image_url)
                if image_file:
                    file_to_send = discord.File(image_file, filename=f"{char_name.replace(' ', '_')}_birthday.png")
                    embed.set_image(url=f"attachment://{char_name.replace(' ', '_')}_birthday.png")
            except Exception as e:
                logger.error(f"Error processing birthday image for {char_name} DM: {e}")
            
            embed.set_footer(text="🎂 Happy Birthday! • Character Birthday Bot")
            
            # Send birthday message EXACTLY like main channel
            if file_to_send:
                await user.send(embed=embed, file=file_to_send)
            else:
                await user.send(embed=embed)
            
            logger.info(f"Sent birthday DM for {char_name} to user")
            
        except Exception as e:
            logger.error(f"Error sending birthday image to user: {e}")
            raise
    
    def _load_subscribers(self):
        """Load subscribers from file"""
        try:
            if os.path.exists(self.notification_file):
                with open(self.notification_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.subscribers = data.get('subscribers', [])
                logger.info(f"Loaded {len(self.subscribers)} notification subscribers")
            else:
                logger.info("No notification file found - starting fresh")
                self.subscribers = []
                
        except Exception as e:
            logger.error(f"Error loading subscribers: {e}")
            self.subscribers = []
    
    def _save_subscribers(self):
        """Save subscribers to file"""
        try:
            data = {
                'subscribers': self.subscribers,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.notification_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.subscribers)} notification subscribers")
            
        except Exception as e:
            logger.error(f"Error saving subscribers: {e}")