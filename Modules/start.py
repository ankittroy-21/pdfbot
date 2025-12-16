from pyrogram.client import Client
from pyrogram import filters
from pyrogram.types import Message
from PIL import Image
import os
import asyncio
from typing import Union

def create_progress_bar(percentage):
    """Create a progress bar with the given percentage"""
    filled_blocks = int(percentage / 10)  # 10% per block
    empty_blocks = 10 - filled_blocks
    bar = "⬢" * filled_blocks + "⬡" * empty_blocks
    return f"[{bar}] {percentage}%"

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
    progress_msg = None
    
    try:
        # Check if the message is a reply to a photo
        if message.reply_to_message and message.reply_to_message.photo:
            # Get the replied photo
            photo = message.reply_to_message.photo
            # Get the file_id of the largest photo size (last in the list is largest)
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
            
            # Send initial progress message
            progress_msg = await message.reply_text(f"Downloading image... {create_progress_bar(0)}")
            
            # Simulate download progress
            for i in range(1, 31):  # 1% to 30% for download
                await asyncio.sleep(0.1)  # Small delay to simulate work
                await progress_msg.edit_text(f"Downloading image... {create_progress_bar(i)}")
            
            # Download the photo with timeout handling
            downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}.jpg")
            
            # Make sure download was successful and it's a string path
            if downloaded_result and isinstance(downloaded_result, str):
                downloaded_path = downloaded_result
                # Update progress message to converting and show progress
                await progress_msg.edit_text(f"Converting to PDF... {create_progress_bar(30)}")
                
                # Simulate conversion progress
                for i in range(31, 66):  # 31% to 65% for conversion
                    await asyncio.sleep(0.1)  # Small delay to simulate work
                    await progress_msg.edit_text(f"Converting to PDF... {create_progress_bar(i)}")
                
                # Convert image to PDF
                img = Image.open(downloaded_path)
                pdf_path = pdf_filename  # Use the user-specified name
                img.save(pdf_path, "PDF")
                
                # Update progress message to uploading and show progress
                await progress_msg.edit_text(f"Uploading PDF... {create_progress_bar(6)}")
                
                # Simulate upload progress
                for i in range(67, 101):  # 67% to 100% for upload
                    await asyncio.sleep(0.05)  # Small delay to simulate work
                    await progress_msg.edit_text(f"Uploading PDF... {create_progress_bar(i)}")
                
                # Send the PDF back to the user
                await message.reply_document(pdf_path, caption=f"Here's your PDF: {pdf_filename}")
                
                # Clean up temporary files
                os.remove(downloaded_path)
                os.remove(pdf_path)
                # Set to None after deletion to avoid trying to delete again
                downloaded_path = None
                pdf_path = None
                
                # Delete the progress message
                await progress_msg.delete()
                
            else:
                await message.reply_text("Failed to download the image.")
                if progress_msg:
                    await progress_msg.delete()
        
        # If not replying to a photo, show usage
        else:
            await message.reply_text(
                "Please reply to an image with /pdf command.\n\n"
                "Usage:\n"
                "- Reply to an image with /pdf to convert with default name (Pdfio.pdf)\n"
                "- Use /pdf filename to specify a custom name for the PDF"
            )
        
    except TimeoutError:
        await message.reply_text("Download timed out. Please try again with a smaller image.")
        if progress_msg:
            await progress_msg.delete()
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")
        if progress_msg:
            try:
                await progress_msg.delete()
            except:
                pass
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