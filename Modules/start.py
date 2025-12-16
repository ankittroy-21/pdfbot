from pyrogram.client import Client
from pyrogram import filters
from pyrogram.types import Message
from PIL import Image
import os
from typing import Union

# Define the handler functions
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Hello! I'm a PDF bot. Send me an image and use /pdf command to convert it to PDF!\n\n"
        "Usage:\n"
        "- Reply to an image with /pdf to convert with default name (Pdfio.pdf)\n"
        "- Use /pdf filename to specify a custom name for the PDF"
    )

# Handler for /pdf command
async def pdf_command_handler(client: Client, message: Message):
    downloaded_path = None
    pdf_path = None
    
    try:
        # Check if the message is a reply to a photo
        if message.reply_to_message and message.reply_to_message.photo:
            # Get the replied photo
            photo = message.reply_to_message.photo
            file_id = photo.file_id
            
            # Extract filename from command if provided
            command_parts = message.text.split(" ", 1)
            if len(command_parts) > 1:
                pdf_filename = command_parts[1].strip()
                # Ensure the filename ends with .pdf
                if not pdf_filename.lower().endswith('.pdf'):
                    pdf_filename += '.pdf'
            else:
                pdf_filename = "Pdfio.pdf"
            
            # Download the photo
            downloaded_result = await client.download_media(file_id, f"temp_{file_id}.jpg")
            
            # Make sure download was successful and it's a string path
            if downloaded_result and isinstance(downloaded_result, str):
                downloaded_path = downloaded_result
                # Convert image to PDF
                img = Image.open(downloaded_path)
                pdf_path = pdf_filename  # Use the user-specified name
                img.save(pdf_path, "PDF")
                
                # Send the PDF back to the user
                await message.reply_document(pdf_path, caption=f"Here's your PDF: {pdf_filename}")
                
                # Clean up temporary files
                os.remove(downloaded_path)
                os.remove(pdf_path)
                # Set to None after deletion to avoid trying to delete again
                downloaded_path = None
                pdf_path = None
            else:
                await message.reply_text("Failed to download the image.")
        
        # If not replying to a photo, show usage
        else:
            await message.reply_text(
                "Please reply to an image with /pdf command.\n\n"
                "Usage:\n"
                "- Reply to an image with /pdf to convert with default name (Pdfio.pdf)\n"
                "- Use /pdf filename to specify a custom name for the PDF"
            )
        
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")
        # Clean up any temporary files if they exist
        try:
            if downloaded_path and isinstance(downloaded_path, str) and os.path.exists(downloaded_path):
                os.remove(downloaded_path)
        except:
            pass
        try:
            if pdf_path and isinstance(pdf_path, str) and os.path.exists(pdf_path):
                os.remove(pdf_path)
        except:
            pass

# Register the handlers directly
def register(app):
    from pyrogram.handlers import message_handler
    app.add_handler(message_handler.MessageHandler(start_command, filters.command("start")))
    app.add_handler(message_handler.MessageHandler(pdf_command_handler, filters.command("pdf")))