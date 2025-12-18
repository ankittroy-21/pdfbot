"""Start command handler"""

from pyrogram.client import Client
from pyrogram.types import Message

async def start_command(client: Client, message: Message):
    await message.reply_text(
        "📄 **PDF Bot**\n\n"
        "Welcome! I'm a professional PDF conversion bot that helps you convert images to PDF files.\n\n"
        "Use /help to see all available commands."
    )

async def help_command(client: Client, message: Message):
    help_text = (
        "📋 **Available Commands**\n\n"
        "🔹 `/start` - Display welcome message\n"
        "🔹 `/help` - Show this help message\n\n"
        "**Single Image to PDF:**\n"
        "🔹 `/pdf [filename]` - Reply to an image to convert it to PDF\n\n"
        "**Multiple Images to PDF:**\n"
        "1️⃣ Send `/multipdf [filename]` to start collecting\n"
        "2️⃣ Send your images (one by one or as album)\n"
        "3️⃣ Click **Done** button when finished\n"
        "4️⃣ Choose A4 or Auto-Size mode\n\n"
        "**PDF Compression:**\n"
        "🔹 `/compress [filename]` - Reply to a PDF to compress it\n\n"
        "**Other Commands:**\n"
        "🔹 `/cancel` - Cancel ongoing multi-PDF collection"
    )
    await message.reply_text(help_text)