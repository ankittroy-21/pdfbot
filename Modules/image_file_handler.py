"""Image file handler for processing images sent as documents"""

import os
import asyncio
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from .core import active_tasks, create_progress_bar, ColorNormalizer
from .rate_limiter import pdf_rate_limiter
from .async_file_handler import AsyncFileHandler

# Common image file extensions and MIME types
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif', 
    '.gif', '.ico', '.svg', '.eps', '.raw', '.cr2', '.nef', '.arw'
}

IMAGE_MIME_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 
    'image/webp', 'image/tiff', 'image/gif', 'image/x-icon',
    'image/svg+xml', 'image/vnd.adobe.photoshop'
}


async def is_valid_image_file(message: Message) -> bool:
    """Check if the message contains a valid image file"""
    if not message.document:
        return False
    
    document = message.document
    file_name = document.file_name.lower() if document.file_name else ""
    mime_type = document.mime_type.lower() if document.mime_type else ""
    
    # Check by file extension
    file_ext = os.path.splitext(file_name)[1]
    if file_ext in IMAGE_EXTENSIONS:
        return True
    
    # Check by MIME type
    if mime_type in IMAGE_MIME_TYPES:
        return True
    
    return False


async def image_file_handler(client: Client, message: Message):
    """Handle image files sent as documents"""
    user_id = message.from_user.id
    
    # Check rate limit
    is_allowed, wait_seconds = pdf_rate_limiter.check_rate_limit(user_id)
    if not is_allowed:
        await message.reply_text(
            f"⏱️ **Rate limit exceeded!**\n\n"
            f"Please wait {wait_seconds} seconds before trying again.\n"
            f"This prevents server overload and ensures fair usage for all users."
        )
        return

    # Check if this is a reply to an image file
    if message.reply_to_message and message.reply_to_message.document:
        if await is_valid_image_file(message.reply_to_message):
            # Extract filename from command if provided
            command_parts = message.text.split(" ", 1)
            if len(command_parts) > 1:
                pdf_filename = command_parts[1].strip()
                # Ensure the filename ends with .pdf
                if not pdf_filename.lower().endswith('.pdf'):
                    pdf_filename += '.pdf'
            else:
                # Generate filename from original image name
                original_name = message.reply_to_message.document.file_name
                if original_name:
                    base_name = os.path.splitext(original_name)[0]
                    pdf_filename = f"{base_name}.pdf"
                else:
                    pdf_filename = None # Will generate unique name in convert_image_to_pdf function
            
            # Generate task ID for cancellation
            task_id = f"convert_doc_{message.reply_to_message.id}"
            await convert_image_file_to_pdf(client, message.reply_to_message, message, pdf_filename, task_id)
        else:
            # Not an image file, ignore or send helpful message
            await message.reply_text("Please reply to an image file with /pdf command.")
    else:
        # If not replying to an image file, explain the usage
        await message.reply_text(
            "Please reply to an image file with /pdf command.\n\n"
            "Supported formats: JPG, PNG, BMP, WEBP, TIFF, GIF, and others.\n\n"
            "Usage:\n"
            "- Reply to an image file with /pdf to convert with unique name\n"
            "- Use /pdf filename to specify a custom name for the PDF"
        )


async def convert_image_file_to_pdf(client, image_message, reply_message, pdf_filename=None, task_id=None):
    """Convert image file (sent as document) to PDF with compression"""
    downloaded_path = None
    pdf_path = None
    progress_msg = None
    
    # Generate task ID if not provided
    if not task_id:
        task_id = f"convert_doc_{image_message.id}"
    
    # Register task for cancellation
    active_tasks[task_id] = {'cancelled': False, 'progress': 0}
    
    try:
        # Get the document
        document = image_message.document
        file_id = document.file_id
        
        # Get original filename for default PDF name if not provided
        original_name = document.file_name or f"image_{file_id}"
        if not pdf_filename:
            base_name = os.path.splitext(original_name)[0]
            pdf_filename = f"{base_name}.pdf"
        
        # Create cancel button
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_convert_{task_id}")]
        ])
        
        # Send initial progress message with cancel button
        progress_msg = await reply_message.reply_text(
            f"{create_progress_bar(0)}\n\nStatus: Downloading image file...",
            reply_markup=cancel_keyboard
        )
        
        # Check for cancellation before download
        if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
            await progress_msg.edit_text("❌ Conversion cancelled by user.")
            return
        
        # Download the document with timeout handling
        downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}_{original_name}")
        
        # Check for cancellation after download
        if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
            if downloaded_result and isinstance(downloaded_result, str) and os.path.exists(downloaded_result):
                os.remove(downloaded_result)
            await progress_msg.edit_text("❌ Conversion cancelled by user.")
            return
        
        # Make sure download was successful and it's a string path
        if downloaded_result and isinstance(downloaded_result, str):
            downloaded_path = downloaded_result
            # Update progress to converting
            await progress_msg.edit_text(
                f"{create_progress_bar(30)}\n\nStatus: Converting to PDF...",
                reply_markup=cancel_keyboard
            )
            
            # Check for cancellation before conversion
            if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
                os.remove(downloaded_path)
                await progress_msg.edit_text("❌ Conversion cancelled by user.")
                return
            
            # Convert image to PDF with color-aware optimization
            from PIL import Image
            img = Image.open(downloaded_path)
            
            # Initialize color normalizer
            normalizer = ColorNormalizer()
            
            # Normalize image to sRGB color space with proper ICC profile handling
            # This prevents "dull" or "washed out" colors
            img, srgb_profile_bytes = normalizer.normalize(img)
            
            # Check if normalization failed
            if img is None:
                await progress_msg.edit_text("❌ Failed to process image.")
                if downloaded_path and os.path.exists(downloaded_path):
                    os.remove(downloaded_path)
                if task_id in active_tasks:
                    del active_tasks[task_id]
                return
            
            # Check for cancellation after opening image
            if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
                os.remove(downloaded_path)
                await progress_msg.edit_text("❌ Conversion cancelled by user.")
                return
            
            # Update progress
            await progress_msg.edit_text(
                f"{create_progress_bar(50)}\n\nStatus: Optimizing colors...",
                reply_markup=cancel_keyboard
            )
            
            # Check for cancellation
            if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
                os.remove(downloaded_path)
                await progress_msg.edit_text("❌ Conversion cancelled by user.")
                return
            
            # Create PDF using optimized settings
            pdf_path = pdf_filename  # Use the provided filename
            
            # Use PyMuPDF for PDF creation with color preservation
            import fitz  # PyMuPDF
            if fitz is not None:
                # Prepare optimized JPEG with color profile
                temp_img_path = f"temp_{file_id}_for_pdf.jpg"
                
                # Aggressive optimization for smaller file size while maintaining quality
                # Balance between quality and compression as per research
                max_dimension = 2000  # Reduced resolution for smaller files
                width, height = img.size
                if width > max_dimension or height > max_dimension:
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save with optimized settings - aggressive compression
                save_kwargs = {
                    'format': 'JPEG',
                    'quality': 75,           # Good quality, better compression
                    'optimize': True,        # Optimize Huffman tables
                    'progressive': True,     # Progressive JPEG
                    'subsampling': '4:2:0'   # Standard chroma subsampling (smaller files)
                }
                
                # Embed sRGB profile if available
                if srgb_profile_bytes:
                    save_kwargs['icc_profile'] = srgb_profile_bytes
                
                img.save(temp_img_path, **save_kwargs)
                
                # Check for cancellation before creating PDF
                if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
                    os.remove(downloaded_path)
                    os.remove(temp_img_path)
                    await progress_msg.edit_text("❌ Conversion cancelled by user.")
                    return
                
                # Create a new PDF document using PyMuPDF for better compression
                doc = fitz.open()
                
                # Get image dimensions after resize
                img_width, img_height = img.size
                
                # Create a new page with the same dimensions as the image
                page = doc.new_page(width=img_width, height=img_height)
                
                # Insert the image into the PDF page
                page.insert_image(page.rect, filename=temp_img_path)
                
                # Save with maximum compression settings
                doc.save(pdf_path,
                         garbage=4,                # Maximum garbage collection
                         deflate=True,             # Deflate compression
                         clean=True)               # Clean content streams
                doc.close()
                
                # Remove the temporary image file
                os.remove(temp_img_path)
                
                # Update progress - conversion complete
                await progress_msg.edit_text(
                    f"{create_progress_bar(90)}\n\nStatus: Finalizing...",
                    reply_markup=cancel_keyboard
                )
            else:
                # Fallback to PIL with optimized settings
                # Aggressive optimization for smaller file size
                max_dimension = 2000
                width, height = img.size
                if width > max_dimension or height > max_dimension:
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save as PDF with aggressive compression settings
                save_kwargs = {
                    'format': 'PDF',
                    'resolution': 100.0,     # Lower resolution for smaller files
                    'save_all': True,
                    'optimize': True,
                    'quality': 75            # Aggressive compression
                }
                
                # Embed sRGB profile if available
                if srgb_profile_bytes:
                    save_kwargs['icc_profile'] = srgb_profile_bytes
                
                img.save(pdf_path, **save_kwargs)
            
            # Update progress to uploading
            await progress_msg.edit_text(
                f"{create_progress_bar(90)}\n\nStatus: Uploading PDF...",
                reply_markup=cancel_keyboard
            )
            
            # Final cancellation check before upload
            if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
                os.remove(downloaded_path)
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                await progress_msg.edit_text("❌ Conversion cancelled by user.")
                return
            
            # Send the PDF back to the user
            await reply_message.reply_document(pdf_path, caption=f"Here's your PDF: {pdf_filename}")
            
            # Clean up temporary files immediately after upload using async file handler
            # Wait a moment for file handles to be released
            await asyncio.sleep(0.5)
            
            # Delete files asynchronously
            files_to_delete = []
            if downloaded_path and os.path.exists(downloaded_path):
                files_to_delete.append(downloaded_path)
            if pdf_path and os.path.exists(pdf_path):
                files_to_delete.append(pdf_path)
            
            if files_to_delete:
                await AsyncFileHandler.delete_files(files_to_delete)
            
            downloaded_path = None
            pdf_path = None
            
            # Delete the progress message
            await progress_msg.delete()
            
            # Clean up task from active tasks
            if task_id in active_tasks:
                del active_tasks[task_id]
            
        else:
            await reply_message.reply_text("Failed to download the image file.")
            if progress_msg:
                try:
                    await progress_msg.delete()
                except:
                    pass

    except TimeoutError:
        await reply_message.reply_text("Download timed out. Please try again with a smaller image file.")
        if progress_msg:
            try:
                await progress_msg.delete()
            except:
                pass
        # Clean up task
        if task_id in active_tasks:
            del active_tasks[task_id]
    except Exception as e:
        await reply_message.reply_text(f"An error occurred: {str(e)}")
        if progress_msg:
            try:
                await progress_msg.delete()
            except:
                pass
        # Clean up task
        if task_id in active_tasks:
            del active_tasks[task_id]
        # Clean up any temporary files if they exist using async handler
        files_to_cleanup = []
        if downloaded_path and isinstance(downloaded_path, str) and os.path.exists(downloaded_path):
            files_to_cleanup.append(downloaded_path)
        if pdf_path and isinstance(pdf_path, str) and os.path.exists(pdf_path):
            files_to_cleanup.append(pdf_path)
        
        if files_to_cleanup:
            await AsyncFileHandler.delete_files(files_to_cleanup)