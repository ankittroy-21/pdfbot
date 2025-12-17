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
        "🔹 `/compress [filename]` - Reply to a PDF to compress it\n\n"
        "**How to use:**\n"
        "📷 *Image to PDF:*\n"
        "1. Send or forward an image to the chat\n"
        "2. Reply to that image with `/pdf` to convert (creates Pdfio.pdf)\n"
        "3. Or use `/pdf MyFile` to specify a custom name\n\n"
        "📄 *PDF Compression:*\n"
        "1. Send a PDF file to the bot\n"
        "2. Reply to that PDF with `/compress` to compress it\n"
        "3. Or use `/compress filename` to specify a custom name for the compressed PDF"
    )
    await message.reply_text(help_text)