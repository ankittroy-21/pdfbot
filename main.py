import os
from pyrogram.client import Client
from pyrogram import filters
from config import API_ID, API_HASH, BOT_TOKEN
from Modules.register import register

# Initialize the bot client
app = Client(
    "pdf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=1  # Reduce sleep threshold to handle API calls more efficiently
)

# Register handlers
register(app)

if __name__ == "__main__":
    print("🤖 Bot has started!")
    try:
        app.run()
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print("\nIf you're seeing a SESSION_REVOKED error:")
        print("1. Check if you've terminated all other Telegram sessions from @BotFather")
        print("2. Delete the pdf_bot.session file in this directory")
        print("3. Restart the bot")
        print("\nIf you're seeing a CONNECTION_FAILED error:")
        print("1. Check your internet connection")
        print("2. Make sure your API credentials are correct")
        print("3. Verify that your bot token is valid")