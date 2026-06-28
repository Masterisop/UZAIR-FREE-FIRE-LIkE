# === api/index.py ===
# Vercel Serverless Function Entry Point

from flask import Flask, request, jsonify
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your existing code
from like_api import app

# Vercel requires the app to be exported as 'app'
# The Flask app is already defined in like_api.py

# If you need to handle async, wrap accordingly
