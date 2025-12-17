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
        "🔹 `/help` - Show this help message\n"
        "🔹 `/pdf [filename]` - Reply to an image to convert it to PDF\n"
        "🔹 `/multipdf [filename]` - Collect multiple images and convert to single PDF\n"
        "🔹 `/compress [filename]` - Reply to a PDF to compress it"
    )
    await message.reply_text(help_text)