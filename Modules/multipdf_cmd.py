"""Multiple images to PDF conversion command handler"""

import os
import asyncio
import time
from pyrogram.client import Client
from pyrogram.types import Message
from PIL import Image
import fitz  # PyMuPDF for better PDF creation
from .core import create_progress_bar, ColorNormalizer

# Dictionary to store collected images for each user
collected_images_store = {}

async def multipdf_command_handler(client: Client, message: Message):
    """Start collecting images for multi-image PDF creation"""
    user_id = message.from_user.id
    
    # Initialize the collection for this user
    if user_id not in collected_images_store:
        collected_images_store[user_id] = []
    
    # Clear any previously collected images
    collected_images_store[user_id] = []
    
    # Extract filename and page mode from command
    # Format: /multipdf [a4|autofit] [filename]
    command_parts = message.text.split()
    page_mode = "a4"  # Default to A4
    pdf_filename = None
    
    if len(command_parts) > 1:
        # Check if first argument is page mode
        if command_parts[1].lower() in ["a4", "autofit"]:
            page_mode = command_parts[1].lower()
            # Check for filename after mode
            if len(command_parts) > 2:
                pdf_filename = " ".join(command_parts[2:])
        else:
            # First argument is filename, use default A4 mode
            pdf_filename = " ".join(command_parts[1:])
    
    # Process filename
    if pdf_filename:
        pdf_filename = pdf_filename.strip()
        # Ensure the filename ends with .pdf
        if not pdf_filename.lower().endswith('.pdf'):
            pdf_filename += '.pdf'
    else:
        # Generate a unique filename based on user ID and timestamp
        pdf_filename = f"MULTIPDF_{message.from_user.id}_{int(time.time())}.pdf"
    
    # Store the filename and page mode for later use
    collected_images_store[f"{user_id}_filename"] = pdf_filename
    collected_images_store[f"{user_id}_pagemode"] = page_mode
    
    mode_description = "A4 standard size" if page_mode == "a4" else "Auto-fit to largest image"
    
    await message.reply_text(
        f"📸 **Multi-Image PDF Collection Started**\n\n"
        f"Page Mode: `{mode_description}`\n"
        f"PDF filename: `{pdf_filename}`\n\n"
        f"Send images to collect them for PDF creation.\n"
        f"When done, use `/done` to create the PDF.\n"
        f"Or use `/cancel` to cancel the process.\n\n"
        f"💡 **Usage:**\n"
        f"`/multipdf` - A4 with auto name\n"
        f"`/multipdf a4 myfile` - A4 with custom name\n"
        f"`/multipdf autofit` - Auto-fit to largest image\n"
        f"`/multipdf autofit myfile` - Auto-fit with custom name"
    )

async def collect_image_handler(client: Client, message: Message):
    """Collect images for multi-image PDF creation"""
    user_id = message.from_user.id
    
    # Check if user has started the collection process
    if user_id not in collected_images_store or f"{user_id}_filename" not in collected_images_store:
        # If not started, inform the user
        await message.reply_text(
            "📸 To collect images for a multi-image PDF:\n"
            "1. Use `/multipdf` to start the collection process\n"
            "2. Send images to be collected\n"
            "3. Use `/done` to create the PDF\n"
            "4. Or use `/cancel` to cancel the process"
        )
        return
    
    # Get the photo
    photo = message.photo
    # Get the file_id of the largest photo size (last in the list is largest)
    file_id = photo.file_id
    
    # Download the photo
    downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}.jpg")
    
    if downloaded_result and isinstance(downloaded_result, str):
        # Add the downloaded image path to the collection
        collected_images_store[user_id].append(downloaded_result)
        
        # Notify user about the collection
        image_count = len(collected_images_store[user_id])
        await message.reply_text(f"✅ Image collected ({image_count} total). Continue sending images or use `/done` to create PDF.")
    else:
        await message.reply_text("❌ Failed to download the image.")

async def done_command_handler(client: Client, message: Message):
    """Process collected images and create a single PDF"""
    user_id = message.from_user.id
    
    # Check if user has collected any images
    if user_id not in collected_images_store or len(collected_images_store[user_id]) == 0:
        await message.reply_text("❌ No images collected. Use `/multipdf` to start collecting images.")
        return
    
    # Get the collected images
    collected_images = collected_images_store[user_id]
    
    # Get the filename and page mode for the PDF
    pdf_filename = collected_images_store.get(f"{user_id}_filename", f"MULTIPDF_{user_id}_{int(time.time())}.pdf")
    page_mode = collected_images_store.get(f"{user_id}_pagemode", "a4")
    
    # Create progress message
    progress_msg = None
    optimized_image_paths = []
    
    try:
        progress_msg = await message.reply_text(f"{create_progress_bar(0)}\n\nStatus: Processing images...")
        
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
            await message.reply_text("❌ No valid images to process.")
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
                
                # Check if image needs padding/centering
                if img_width < target_width or img_height < target_height:
                    # Create a white canvas of target size
                    canvas = Image.new('RGB', (target_width, target_height), 'white')
                    
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
                    
                    # Use the padded image for PDF
                    page = doc.new_page(width=target_width, height=target_height)
                    page.insert_image(page.rect, filename=padded_path)
                    
                    # Clean up padded image
                    try:
                        os.remove(padded_path)
                    except:
                        pass
                else:
                    # Image fits perfectly or is larger - use as-is
                    img.close()
                    page = doc.new_page(width=img_width, height=img_height)
                    page.insert_image(page.rect, filename=img_path)
            
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
                
                # Pad to target size if needed
                if img.width < target_width or img.height < target_height:
                    canvas = Image.new('RGB', (target_width, target_height), 'white')
                    x_offset = (target_width - img.width) // 2
                    y_offset = (target_height - img.height) // 2
                    canvas.paste(img, (x_offset, y_offset))
                    img.close()
                    processed_images.append(canvas)
                else:
                    processed_images.append(img)
            
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
        mode_text = "A4 Standard" if page_mode == "a4" else "Auto-Fit"
        await message.reply_document(
            pdf_filename,
            caption=f"📚 Multi-Image PDF: {pdf_filename}\n"
                    f"Contains {len(optimized_image_paths)} images.\n"
                    f"Page Mode: {mode_text}"
        )
        
        # Update progress - complete
        await progress_msg.edit_text(f"{create_progress_bar(100)}\n\nStatus: Complete!")
        await asyncio.sleep(1)  # Small delay before deleting progress message
        if progress_msg:
            await progress_msg.delete()
        
        # Clean up temporary image files with retry logic
        for img_path in collected_images:
            for attempt in range(3):
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                    break
                except:
                    if attempt < 2:
                        await asyncio.sleep(0.3)
        
        # Clean up optimized image files
        for img_path in optimized_image_paths:
            for attempt in range(3):
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                    break
                except:
                    if attempt < 2:
                        await asyncio.sleep(0.3)
        
        # Clean up the generated PDF file after sending
        for attempt in range(3):
            try:
                if os.path.exists(pdf_filename):
                    os.remove(pdf_filename)
                break
            except:
                if attempt < 2:
                    await asyncio.sleep(0.3)
        
        # Clear the collection for this user
        collected_images_store.pop(user_id, None)
        collected_images_store.pop(f"{user_id}_filename", None)
        collected_images_store.pop(f"{user_id}_pagemode", None)
        
    except Exception as e:
        await message.reply_text(f"❌ An error occurred while creating the PDF: {str(e)}")
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
        
        # Clear the collection for this user
        collected_images_store.pop(user_id, None)
        collected_images_store.pop(f"{user_id}_filename", None)
        collected_images_store.pop(f"{user_id}_pagemode", None)

async def cancel_command_handler(client: Client, message: Message):
    """Cancel the multi-image PDF collection process"""
    user_id = message.from_user.id
    
    # Check if user has started the collection process
    if user_id not in collected_images_store:
        await message.reply_text("❌ No collection process to cancel.")
        return
    
    # Get the collected images to clean them up
    collected_images = collected_images_store.get(user_id, [])
    
    # Clean up temporary image files
    for img_path in collected_images:
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except:
            pass  # Ignore errors if file is still locked
    
    # Clear the collection for this user
    collected_images_store.pop(user_id, None)
    collected_images_store.pop(f"{user_id}_filename", None)
    collected_images_store.pop(f"{user_id}_pagemode", None)
    
    await message.reply_text("✅ Multi-image PDF collection cancelled. All collected images have been cleared.")
