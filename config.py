import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables with validation
api_id_str = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

# Validate that all required environment variables are set
if not api_id_str or not api_hash or not bot_token:
    raise ValueError("Missing required environment variables. Please check your .env file.")

# Convert API_ID to integer
try:
    API_ID = int(api_id_str)
except (ValueError, TypeError):
    raise ValueError("API_ID must be a valid integer")

API_HASH = api_hash
BOT_TOKEN = bot_token