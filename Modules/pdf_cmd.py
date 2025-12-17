"""PDF conversion command handler"""

from pyrogram.client import Client
from pyrogram.types import Message
from .core import convert_image_to_pdf

async def pdf_command_handler(client: Client, message: Message):
    """Handle /pdf command when user replies to an image"""
    # If this is a reply to an image, process it
    if message.reply_to_message and message.reply_to_message.photo:
        # Extract filename from command if provided
        command_parts = message.text.split(" ", 1)
        if len(command_parts) > 1:
            pdf_filename = command_parts[1].strip()
            # Ensure the filename ends with .pdf
            if not pdf_filename.lower().endswith('.pdf'):
                pdf_filename += '.pdf'
        else:
            pdf_filename = None  # Will generate unique name in convert_image_to_pdf function
        
        await convert_image_to_pdf(client, message.reply_to_message, message, pdf_filename)
    else:
        # If not replying to an image, explain the usage
        await message.reply_text(
            "Please reply to an image with /pdf command.\n\n"
            "Usage:\n"
            "- Reply to an image with /pdf to convert with unique name\n"
            "- Use /pdf filename to specify a custom name for the PDF"
        )

async def image_handler(client: Client, message: Message):
    """Handle direct image messages (automatic conversion)"""
    await convert_image_to_pdf(client, message, message)