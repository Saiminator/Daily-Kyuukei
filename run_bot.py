#!/usr/bin/env python3
"""
Simple launcher script for the Discord bot
Use this on your Raspberry Pi
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main function
from main import main
import asyncio

if __name__ == "__main__":
    print("Starting Discord Character Bot...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)