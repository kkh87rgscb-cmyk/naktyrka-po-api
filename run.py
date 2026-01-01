#!/usr/bin/env python3
"""Entry point script for the Steam SMM Telegram Bot."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import run

if __name__ == "__main__":
    run()
