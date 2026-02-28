#!/bin/bash
# Raspberry Pi Setup Script for Discord Bot

echo "Setting up Discord Character Bot on Raspberry Pi..."

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip if not already installed
echo "Installing Python dependencies..."
sudo apt install python3 python3-pip python3-venv -y

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv bot_env
source bot_env/bin/activate

# Install Python packages
echo "Installing Python packages..."
pip install --upgrade pip
pip install discord.py>=2.3.0
pip install requests>=2.31.0
pip install beautifulsoup4>=4.12.0
pip install schedule>=1.2.0
pip install python-dotenv>=1.0.0
pip install Pillow>=10.0.0
pip install aiohttp>=3.8.0
pip install pytz>=2023.3

echo "Dependencies installed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env"
echo "2. Fill in your Discord bot token and channel ID in .env"
echo "3. Run: python3 run_bot.py"