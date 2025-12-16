import os
from pyrogram.client import Client
from pyrogram import filters
from config import API_ID, API_HASH, BOT_TOKEN
from Modules.start import register

# Initialize the bot client
app = Client(
    "pdf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Register handlers
register(app)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()