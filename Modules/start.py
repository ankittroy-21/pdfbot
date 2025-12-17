# Import fitz (PyMuPDF) for better compression at the top level
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    fitz = None  # Set to None so it's defined
    HAS_PYMUPDF = False

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
        "📄 **PDF Bot**\n\n"
        "Welcome! I'm a professional PDF conversion bot that helps you convert images to PDF files.\n\n"
        "Use /help to see all available commands."
    )

# Handler for /help command
async def help_command(client: Client, message: Message):
    help_text = (
        "📋 **Available Commands**\n\n"
        "🔹 `/start` - Display welcome message\n"
        "🔹 `/help` - Show this help message\n"
        "🔹 `/pdf [filename]` - Reply to an image to convert it to PDF\n\n"
        "**How to use:**\n"
        "1. Send an image to the bot\n"
        "2. Reply to that image with `/pdf` to convert with unique default name\n"
        "3. Or use `/pdf filename` to specify a custom name for the PDF"
    )
    await message.reply_text(help_text)

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
                # Use a unique filename based on user ID and timestamp to avoid conflicts
                import time
                pdf_filename = f"PDF_{message.from_user.id}_{int(time.time())}.pdf"
            
            # Send initial progress message with progress bar at top and status at bottom
            progress_msg = await message.reply_text(f"{create_progress_bar(0)}\n\nStatus: Downloading image...")
            
            # Simulate download progress
            for i in range(1, 31): # 1% to 30% for download
                await asyncio.sleep(0.1)  # Small delay to simulate work
                await progress_msg.edit_text(f"{create_progress_bar(i)}\n\nStatus: Downloading image...")
            
            # Download the photo with timeout handling
            downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}.jpg")
            
            # Make sure download was successful and it's a string path
            if downloaded_result and isinstance(downloaded_result, str):
                downloaded_path = downloaded_result
                # Update progress message to converting and show progress
                await progress_msg.edit_text(f"{create_progress_bar(30)}\n\nStatus: Converting to PDF...")
                
                # Simulate conversion progress
                for i in range(31, 66):  # 31% to 65% for conversion
                    await asyncio.sleep(0.1)  # Small delay to simulate work
                    await progress_msg.edit_text(f"{create_progress_bar(i)}\n\nStatus: Converting to PDF...")
                
                # Convert image to PDF with advanced optimization based on the reference code
                img = Image.open(downloaded_path)
                
                # Optimize the image before creating PDF
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Convert to RGB if the image has transparency
                    img = img.convert('RGB')
                
                # Resize image to an optimal size for PDFs while maintaining quality
                original_width, original_height = img.size
                if original_width > 1600 or original_height > 1600:
                    # Maintain aspect ratio
                    img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                
                # Create PDF using optimized settings
                pdf_path = pdf_filename  # Use the user-specified name
                
                # Use PyMuPDF if available for better compression, otherwise use PIL
                if HAS_PYMUPDF and fitz is not None:
                    # Save the image as JPEG first with optimized quality
                    temp_img_path = f"temp_{file_id}_for_pdf.jpg"
                    img.save(temp_img_path, "JPEG", quality=65, optimize=True)
                    
                    # Create a new PDF document using PyMuPDF for better compression
                    doc = fitz.open()
                    
                    # Get image dimensions
                    img_width, img_height = img.size
                    
                    # Create a new page with the same dimensions as the image
                    page = doc.new_page(width=img_width, height=img_height)
                    
                    # Insert the image into the PDF page
                    page.insert_image(page.rect, filename=temp_img_path)
                    
                    # Save the document with maximum compression settings
                    doc.save(pdf_path,
                             deflate_images=True,    # Compress images
                             deflate_fonts=True,     # Compress fonts
                             garbage=4,              # Aggressive garbage collection
                             deflate=True)           # General compression
                    doc.close()
                    
                    # Remove the temporary image file
                    os.remove(temp_img_path)
                    
                    # Additional compression step: optimize the PDF further if possible
                    # Close any handles before re-optimization
                    try:
                        # Small delay to ensure file handles are released
                        import time
                        time.sleep(0.1)
                        
                        # Reopen the PDF and save again with additional optimizations
                        re_optimized_doc = fitz.open(pdf_path)
                        re_optimized_doc.save(pdf_path,
                                             deflate_images=True,
                                             deflate_fonts=True,
                                             garbage=4,
                                             deflate=True)
                        re_optimized_doc.close()
                        # Explicitly delete the variable to ensure file handle is released
                        del re_optimized_doc
                        
                        # Small delay to ensure file handles are released before next operation
                        time.sleep(0.1)
                    except:
                        pass # If re-optimization fails, continue with original
                else:
                    # Fallback to PIL with optimized settings
                    img.save(pdf_path, "PDF",
                             resolution=96.0,  # Standard screen resolution for smaller size
                             save_all=True,
                             optimize=True,
                             # Additional compression parameters
                             compress_type="JPEG",  # Use JPEG compression for images
                             quality=70)  # Good balance between quality and size
                
                # Update progress message to uploading and show progress
                await progress_msg.edit_text(f"{create_progress_bar(66)}\n\nStatus: Uploading PDF...")
                
                # Simulate upload progress
                for i in range(67, 101): # 67% to 100% for upload
                    await asyncio.sleep(0.05) # Small delay to simulate work
                    await progress_msg.edit_text(f"{create_progress_bar(i)}\n\nStatus: Uploading PDF...")
                
                # Send the PDF back to the user
                await message.reply_document(pdf_path, caption=f"Here's your PDF: {pdf_filename}")
                
                # Small delay to ensure file handles are released after sending
                await asyncio.sleep(0.5)
                
                # Clean up temporary files
                try:
                    if downloaded_path and os.path.exists(downloaded_path):
                        os.remove(downloaded_path)
                except:
                    pass # Ignore errors if file is still locked
                
                try:
                    if pdf_path and os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except:
                    pass  # Ignore errors if file is still locked
                
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
    app.add_handler(message_handler.MessageHandler(help_command, filters.command("help")))
    app.add_handler(message_handler.MessageHandler(pdf_command_handler, filters.command("pdf")))