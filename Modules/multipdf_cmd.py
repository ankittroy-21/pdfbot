"""Multiple images to PDF conversion command handler"""

import os
import asyncio
import time
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image
import fitz  # PyMuPDF for better PDF creation
from .core import create_progress_bar, ColorNormalizer
from .supabase_client import SupabaseStorage, UserTracker
from .rate_limiter import multipdf_rate_limiter
from .async_file_handler import AsyncFileHandler

# Global session storage adapter (set by main.py)
# Falls back to SupabaseStorage if not set
_session_storage = None

def set_session_storage(storage):
    """Set the global session storage adapter"""
    global _session_storage
    _session_storage = storage

def get_storage():
    """Get the current session storage (Redis or Supabase)"""
    return _session_storage if _session_storage else SupabaseStorage

# Backward compatibility: Keep in-memory store for progress messages
# Session storage is now handled by SessionStorageAdapter in main.py
_progress_messages = {}

async def multipdf_command_handler(client: Client, message: Message):
    """Start collecting images for multi-image PDF creation"""
    user_id = message.from_user.id
    
    # Get session storage adapter (Redis or Supabase)
    storage = get_storage()
    
    # Check rate limit
    is_allowed, wait_seconds = multipdf_rate_limiter.check_rate_limit(user_id)
    if not is_allowed:
        await message.reply_text(
            f"⏱️ **Rate limit exceeded!**\n\n"
            f"Please wait {wait_seconds} seconds before creating more multi-page PDFs.\n"
            f"Multi-PDF processing is resource-intensive, so we limit requests to ensure quality service."
        )
        return
    
    # Track user activity
    await UserTracker.track_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Check if user already has an active session
    existing_session = await storage.get_user_session(user_id)
    if existing_session:
        # Clean up old session completely before starting new one
        await storage.delete_session(existing_session)
        _progress_messages.pop(user_id, None)
        
        # Clean up local temp files for this user
        import shutil
        temp_user_folder = f"downloads/temp_sessions/{existing_session}"
        if os.path.exists(temp_user_folder):
            try:
                shutil.rmtree(temp_user_folder, ignore_errors=True)
            except:
                pass
    
    # Extract optional filename from command
    # Format: /multipdf [filename]
    command_parts = message.text.split()
    pdf_filename = None
    
    if len(command_parts) > 1:
        pdf_filename = " ".join(command_parts[1:]).strip()
        # Ensure the filename ends with .pdf
        if not pdf_filename.lower().endswith('.pdf'):
            pdf_filename += '.pdf'
    else:
        # Generate a unique filename based on user ID and timestamp
        pdf_filename = f"MULTIPDF_{message.from_user.id}_{int(time.time())}.pdf"
    
    # Create new session using adapter (Redis or Supabase)
    session_id = await storage.create_session(user_id)  # type: ignore
    
    await message.reply_text(
        f"📸 **I am ready to convert your images into a single PDF.**\n\n"
        f"📤 Send them now.\n"
        f"✅ Click **Done** button when finished\n\n"
        f"PDF filename: `{pdf_filename}`"
    )

async def collect_image_handler(client: Client, message: Message):
    """Collect images for multi-image PDF creation"""
    user_id = message.from_user.id
    storage = get_storage()
    
    # Check if user has an active session
    session_id = await storage.get_user_session(user_id)
    if not session_id:
        # Silently ignore photos/documents sent without starting /multipdf
        # Users can still use /pdf to convert single images or /compress for PDFs
        return

    downloaded_result = None

    # Handle photo messages
    if message.photo:
        # Get the photo
        photo = message.photo
        # Get the file_id of the largest photo size (last in the list is largest)
        file_id = photo.file_id
        
        # Download the photo
        downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}.jpg")
    # Handle document messages that are valid images
    elif message.document:
        from .image_file_handler import is_valid_image_file
        if await is_valid_image_file(message):
            document = message.document
            file_id = document.file_id
            original_name = document.file_name or f"image_{file_id}"
            # Download the document with its original extension for proper processing
            downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}_{original_name}")

    if downloaded_result and isinstance(downloaded_result, str):
        # Get current image count before adding
        current_images = await storage.get_session_images(session_id)
        order = len(current_images)
        
        # Add to storage (Redis or Supabase)
        await storage.add_image(session_id, downloaded_result, order)
        
        # Delete the temp file immediately after adding to Supabase
        await asyncio.sleep(0.2)
        if os.path.exists(downloaded_result):
            await AsyncFileHandler.delete_file(downloaded_result)
        
        # Get updated count
        image_count = order + 1
        
        # Create/update progress message with Done and Cancel buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Done", callback_data=f"multipdf_done_{user_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_multipdf_collection_{user_id}")
            ]
        ])
        
        # Check if this is the first image - create new progress message
        if user_id not in _progress_messages:
            # Create the progress message for the first time
            progress_msg = await message.reply_text(
                f"📥 **Downloaded {image_count} image(s)**\n"
                f"\n"
                f"Continue sending images or click **Done** to proceed.",
                reply_markup=keyboard
            )
            _progress_messages[user_id] = progress_msg
        else:
            # Update the existing progress message
            progress_msg = _progress_messages[user_id]
            try:
                await progress_msg.edit_text(
                    f"📥 **Downloaded {image_count} image(s)**\n"
                    f"\n"
                    f"Continue sending images or click **Done** to proceed.",
                    reply_markup=keyboard
                )
            except Exception as e:
                # If message was deleted or edit failed, create a new one
                new_progress = await message.reply_text(
                    f"📥 **Downloaded {image_count} image(s)**\n"
                    f"\n"
                    f"Continue sending images or click **Done** to proceed.",
                    reply_markup=keyboard
                )
                _progress_messages[user_id] = new_progress
    elif message.document:
        # If it's a document but not a valid image, just ignore it silently
        # Don't show an error message for non-image documents
        pass

async def done_command_handler(client: Client, message: Message):
    """Show A4/Auto-Size buttons after user has collected images"""
    user_id = message.from_user.id
    
    # Get active session
    session_id = await SupabaseStorage.get_user_session(user_id)
    if not session_id:
        await message.reply_text("❌ No images collected. Use `/multipdf` to start collecting images.")
        return
    
    # Get session details
    session = await SupabaseStorage.get_session(session_id)
    if not session:
        await message.reply_text("❌ Session not found. Please try again.")
        return
    
    # Get image count
    images = await SupabaseStorage.get_session_images(session_id)
    image_count = len(images)
    
    if image_count == 0:
        await message.reply_text("❌ No images collected. Send some images first!")
        return
    
    pdf_filename = session.get('filename', f"MULTIPDF_{user_id}_{int(time.time())}.pdf") if session else f"MULTIPDF_{user_id}_{int(time.time())}.pdf"
    
    # Show A4/Auto-Size buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📄 A4 Standard", callback_data=f"multipdf_a4_{user_id}"),
            InlineKeyboardButton("📐 Auto-Size", callback_data=f"multipdf_auto_{user_id}")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_multipdf_selection_{user_id}")
        ]
    ])
    
    await message.reply_text(
        f"✅ **{image_count} image(s) collected!**\n"
        f"Filename: `{pdf_filename}`\n\n"
        f"📄 **A4 Standard:** Fixed A4 page size (595×842px) with white borders\n"
        f"📐 **Auto-Size:** Best size based on your images\n\n"
        f"Choose your preferred page size:",
        reply_markup=keyboard
    )

async def multipdf_callback_handler(client: Client, callback_query):
    """Handle Done button, A4/Auto-Size button clicks"""
    user_id = callback_query.from_user.id
    callback_data = callback_query.data
    
    # Handle "Done" button - show A4/Auto-Size selection
    if callback_data.startswith("multipdf_done_"):
        # Get active session
        session_id = await SupabaseStorage.get_user_session(user_id)
        if not session_id:
            await callback_query.answer("❌ No images collected.", show_alert=True)
            return
        
        # Update session status to 'awaiting_selection' to prevent auto-cleanup
        await SupabaseStorage.update_session_status(session_id, 'awaiting_selection')
        
        # Get session details and images
        session = await SupabaseStorage.get_session(session_id)
        images = await SupabaseStorage.get_session_images(session_id)
        image_count = len(images)
        
        if image_count == 0:
            await callback_query.answer("❌ No images collected.", show_alert=True)
            return
        
        pdf_filename = session.get('filename', f"MULTIPDF_{user_id}_{int(time.time())}.pdf") if session else f"MULTIPDF_{user_id}_{int(time.time())}.pdf"
        
        # Show A4/Auto-Size buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📄 A4 Standard", callback_data=f"multipdf_a4_{user_id}"),
                InlineKeyboardButton("📐 Auto-Size", callback_data=f"multipdf_auto_{user_id}")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_multipdf_selection_{user_id}")
            ]
        ])
        
        await callback_query.message.edit_text(
            f"✅ **{image_count} image(s) collected!**\n"
            f"Filename: `{pdf_filename}`\n\n"
            f"📄 **A4 Standard:** Fixed A4 page size (595×842px) with white borders\n"
            f"📐 **Auto-Size:** Best size based on your images\n\n"
            f"Choose your preferred page size:",
            reply_markup=keyboard
        )
        await callback_query.answer()
        return
    
    # Parse callback data: multipdf_a4_{user_id} or multipdf_auto_{user_id}
    if callback_data.startswith("multipdf_a4_"):
        page_mode = "a4"
    elif callback_data.startswith("multipdf_auto_"):
        page_mode = "autofit"
    else:
        await callback_query.answer("❌ Invalid selection", show_alert=True)
        return
    
    # Get active session
    session_id = await SupabaseStorage.get_user_session(user_id)
    if not session_id:
        await callback_query.answer("❌ Session expired. Please start again with /multipdf", show_alert=True)
        return
    
    # Refresh session timer (extends by 30 more minutes)
    await SupabaseStorage.update_session_status(session_id, 'processing')
    
    await callback_query.answer("⏳ Creating PDF...")
    
    # Get session details and images
    session = await SupabaseStorage.get_session(session_id)
    collected_images = await SupabaseStorage.get_session_images(session_id)
    
    if not collected_images:
        await callback_query.answer("❌ No images found.", show_alert=True)
        return
    
    # Get the filename for the PDF
    pdf_filename = session.get('filename', f"MULTIPDF_{user_id}_{int(time.time())}.pdf") if session else f"MULTIPDF_{user_id}_{int(time.time())}.pdf"
    
    # Update session status
    await SupabaseStorage.update_session_status(session_id, 'processing')
    
    # Update the message to show processing
    await callback_query.message.edit_text(
        f"⏳ Creating PDF with **{'A4 Standard' if page_mode == 'a4' else 'Auto-Size'}** mode...\n"
        f"Images: {len(collected_images)}"
    )
    
    # Create progress message
    progress_msg = None
    optimized_image_paths = []
    
    try:
        progress_msg = await callback_query.message.reply_text(f"{create_progress_bar(0)}\n\nStatus: Processing images...")
        
        # Update progress - loading images
        await progress_msg.edit_text(f"{create_progress_bar(10)}\n\nStatus: Loading images...")
        
        # Initialize color normalizer for consistent color handling
        normalizer = ColorNormalizer()
        
        # Load and optimize all images with color normalization
        for i, img_path in enumerate(collected_images):
            img = Image.open(img_path)
            
            # Apply color normalization to prevent dull colors
            img, srgb_profile_bytes = normalizer.normalize(img)
            
            if img is None:
                continue
            
            # Optimize size - match single image conversion settings
            max_dimension = 2000
            original_width, original_height = img.size
            if original_width > max_dimension or original_height > max_dimension:
                if original_width > original_height:
                    new_width = max_dimension
                    new_height = int(original_height * (max_dimension / original_width))
                else:
                    new_height = max_dimension
                    new_width = int(original_width * (max_dimension / original_height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized JPEG for PDF embedding
            optimized_path = f"optimized_{i}_{int(time.time())}.jpg"
            save_kwargs = {
                'format': 'JPEG',
                'quality': 75,           # Match single image conversion
                'optimize': True,
                'progressive': True,
                'subsampling': '4:2:0'   # Standard chroma subsampling
            }
            if srgb_profile_bytes:
                save_kwargs['icc_profile'] = srgb_profile_bytes
            
            img.save(optimized_path, **save_kwargs)
            optimized_image_paths.append(optimized_path)
            img.close()
        
        if not optimized_image_paths:
            await callback_query.message.reply_text("❌ No valid images to process.")
            return
        
        # Update progress - creating PDF
        await progress_msg.edit_text(f"{create_progress_bar(40)}\n\nStatus: Creating PDF...")
        
        # Determine target dimensions based on page mode
        if page_mode == "a4":
            # A4 size at 72 DPI: 595 × 842 pixels (portrait)
            target_width = 595
            target_height = 842
        else:
            # Auto-fit: Find the largest dimensions among all images
            max_width = 0
            max_height = 0
            for img_path in optimized_image_paths:
                img = Image.open(img_path)
                if img.width > max_width:
                    max_width = img.width
                if img.height > max_height:
                    max_height = img.height
                img.close()
            target_width = max_width
            target_height = max_height
        
        # Create PDF using PyMuPDF for better control
        if fitz is not None:
            doc = fitz.open()
            
            for img_path in optimized_image_paths:
                img = Image.open(img_path)
                img_width, img_height = img.size
                
                # Always create a canvas at the target size
                canvas = Image.new('RGB', (target_width, target_height), 'white')
                
                # Check if image needs to be resized to fit within target dimensions
                if img_width > target_width or img_height > target_height:
                    # Scale image down to fit within target size while maintaining aspect ratio
                    ratio = min(target_width / img_width, target_height / img_height)
                    new_width = int(img_width * ratio)
                    new_height = int(img_height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    img_width, img_height = new_width, new_height
                
                # Calculate position to center the image
                x_offset = (target_width - img_width) // 2
                y_offset = (target_height - img_height) // 2
                
                # Paste the image onto the canvas
                canvas.paste(img, (x_offset, y_offset))
                img.close()
                
                # Save the padded image temporarily
                padded_path = f"padded_{img_path}"
                canvas.save(padded_path, 'JPEG', quality=75, optimize=True)
                canvas.close()
                
                # Use the padded image for PDF with target dimensions
                page = doc.new_page(width=target_width, height=target_height)
                page.insert_image(page.rect, filename=padded_path)
                
                # Clean up padded image
                try:
                    os.remove(padded_path)
                except:
                    pass
            
            # Save with optimization
            doc.save(
                pdf_filename,
                garbage=4,      # Maximum garbage collection
                deflate=True,   # Compress streams
                clean=True      # Clean content streams
            )
            doc.close()
        else:
            # Fallback to PIL if PyMuPDF not available
            processed_images = []
            
            for img_path in optimized_image_paths:
                img = Image.open(img_path)
                
                # Always create a canvas at the target size
                canvas = Image.new('RGB', (target_width, target_height), 'white')
                
                # Check if image needs to be resized to fit within target dimensions
                if img.width > target_width or img.height > target_height:
                    # Scale image down to fit within target size while maintaining aspect ratio
                    ratio = min(target_width / img.width, target_height / img.height)
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Calculate position to center the image
                x_offset = (target_width - img.width) // 2
                y_offset = (target_height - img.height) // 2
                
                # Paste the image onto the canvas
                canvas.paste(img, (x_offset, y_offset))
                img.close()
                processed_images.append(canvas)
            
            if processed_images:
                processed_images[0].save(
                    pdf_filename,
                    "PDF",
                    resolution=100.0,
                    save_all=True,
                    append_images=processed_images[1:],
                    optimize=True,
                    quality=75
                )
                for img in processed_images:
                    img.close()
        
        # Update progress - uploading
        await progress_msg.edit_text(f"{create_progress_bar(80)}\n\nStatus: Uploading PDF...")
        
        # Send the PDF back to the user
        mode_text = "A4 Standard" if page_mode == "a4" else "Auto-Size"
        await callback_query.message.reply_document(
            pdf_filename,
            caption=f"📚 Multi-Image PDF: {pdf_filename}\n"
                    f"Contains {len(optimized_image_paths)} images.\n"
                    f"Page Mode: {mode_text}"
        )
        
        # Track successful PDF creation
        await UserTracker.increment_pdf_count(user_id)
        
        # Update progress - complete
        await progress_msg.edit_text(f"{create_progress_bar(100)}\n\nStatus: Complete!")
        await asyncio.sleep(1)  # Small delay before deleting progress message
        if progress_msg:
            await progress_msg.delete()
        
        # COMPREHENSIVE CLEANUP - Free all storage
        
        # Wait for file handles to be released
        await asyncio.sleep(0.5)
        
        # Prepare list of all files to delete
        files_to_delete = []
        
        # 1. Add original downloaded images (from Telegram)
        files_to_delete.extend([img for img in collected_images if os.path.exists(img)])
        
        # 2. Add optimized image files
        files_to_delete.extend([img for img in optimized_image_paths if os.path.exists(img)])
        
        # 3. Add the generated PDF file after sending
        if os.path.exists(pdf_filename):
            files_to_delete.append(pdf_filename)
        
        # Delete all files asynchronously
        if files_to_delete:
            await AsyncFileHandler.delete_files(files_to_delete)
        
        # 4. Clean up user-specific temp session folder (downloaded from Supabase)
        import shutil
        temp_session_folder = f"downloads/temp_sessions/{session_id}"
        if os.path.exists(temp_session_folder):
            try:
                shutil.rmtree(temp_session_folder, ignore_errors=True)
                print(f"🗑️ Cleaned up local temp folder: {temp_session_folder}")
            except Exception as e:
                print(f"⚠️ Failed to delete temp folder: {e}")
        
        # 5. Delete session from Supabase (removes Storage files and database records)
        await SupabaseStorage.delete_session(session_id)
        _progress_messages.pop(user_id, None)
        
        print(f"✅ Complete cleanup for session {session_id}")
        
    except Exception as e:
        await callback_query.message.reply_text(f"❌ An error occurred while creating the PDF: {str(e)}")
        if progress_msg:
            try:
                await progress_msg.delete()
            except:
                pass
        
        # Clean up temporary image files in case of error
        for img_path in collected_images:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
            except:
                pass
        
        # Clean up optimized images
        for img_path in optimized_image_paths:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
            except:
                pass
        
        # Clear the session and progress message
        if session_id:
            await SupabaseStorage.delete_session(session_id)
        _progress_messages.pop(user_id, None)

async def handle_multipdf_cancel(client: Client, callback_query):
    """Handle multi-PDF cancel button clicks"""
    data_raw = callback_query.data
    
    # Handle both string and bytes
    if isinstance(data_raw, bytes):
        data = data_raw.decode('utf-8')
    else:
        data = str(data_raw)
    
    # Handle collection cancellation (from progress message)
    if data.startswith("cancel_multipdf_collection_"):
        user_id_str = data.replace("cancel_multipdf_collection_", "")
        user_id = int(user_id_str)
        
        # Clean up session
        session_id = await SupabaseStorage.get_user_session(user_id)
        if session_id:
            # Clean up local files
            images = await SupabaseStorage.get_session_images(session_id)
            for photo_path in images:
                try:
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except:
                    pass
            
            # Clean up temp session folder
            import shutil
            temp_session_folder = f"downloads/temp_sessions/{session_id}"
            if os.path.exists(temp_session_folder):
                try:
                    shutil.rmtree(temp_session_folder, ignore_errors=True)
                except:
                    pass
            
            # Delete from Supabase (Storage + Database)
            await SupabaseStorage.delete_session(session_id)
        _progress_messages.pop(user_id, None)
        
        await callback_query.answer("✅ Cancelled!", show_alert=True)
        try:
            await callback_query.message.edit_text("❌ Multi-PDF collection cancelled.")
        except:
            pass
        return
    
    # Handle selection cancellation (before conversion starts)
    if data.startswith("cancel_multipdf_selection_"):
        user_id_str = data.replace("cancel_multipdf_selection_", "")
        user_id = int(user_id_str)
        
        # Clean up session
        session_id = await SupabaseStorage.get_user_session(user_id)
        if session_id:
            # Clean up local files
            images = await SupabaseStorage.get_session_images(session_id)
            for photo_path in images:
                try:
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except:
                    pass
            
            # Clean up temp session folder
            import shutil
            temp_session_folder = f"downloads/temp_sessions/{session_id}"
            if os.path.exists(temp_session_folder):
                try:
                    shutil.rmtree(temp_session_folder, ignore_errors=True)
                except:
                    pass
            
            # Delete from Supabase (Storage + Database)
            await SupabaseStorage.delete_session(session_id)
        _progress_messages.pop(user_id, None)
        
        await callback_query.answer("✅ Cancelled!", show_alert=True)
        try:
            await callback_query.message.edit_text("❌ Multi-PDF creation cancelled.")
        except:
            pass
        return

async def cancel_command_handler(client: Client, message: Message):
    """Cancel the multi-image PDF collection process"""
    user_id = message.from_user.id
    
    # Check if user has an active session
    session_id = await SupabaseStorage.get_user_session(user_id)
    if not session_id:
        await message.reply_text("❌ No collection process to cancel.")
        return
    
    # Get the collected images to clean them up
    collected_images = await SupabaseStorage.get_session_images(session_id)
    
    # Clean up temporary image files
    for img_path in collected_images:
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except:
            pass  # Ignore errors if file is still locked
    
    # Clear the session and progress message
    await SupabaseStorage.delete_session(session_id)
    _progress_messages.pop(user_id, None)
    
    await message.reply_text("✅ Multi-image PDF collection cancelled. All collected images have been cleared.")
