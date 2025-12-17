"""Core functionality shared across commands"""

from PIL import Image, ImageCms
from io import BytesIO
import os
import asyncio
import fitz  # PyMuPDF
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Active tasks dictionary to track conversions
active_tasks = {}

class ColorNormalizer:
    """
    A robust engine for converting images to standardized sRGB color space
    to prevent 'dull' or 'washed out' colors in PDF generation.
    """
    
    def __init__(self):
        # Create the sRGB profile using Pillow's built-in profile
        self.srgb_profile = ImageCms.createProfile('sRGB')
        
        # Get the profile bytes for embedding
        profile_buffer = BytesIO()
        # Save profile to buffer to get bytes
        try:
            # For newer Pillow versions, we can get bytes directly
            if hasattr(self.srgb_profile, 'tobytes'):
                self.srgb_profile_bytes = self.srgb_profile.tobytes()
            else:
                # Fallback: create a temporary image with the profile and extract it
                temp_img = Image.new('RGB', (1, 1))
                temp_img.info['icc_profile'] = None
                # Build profile bytes manually by transforming a test image
                # Actually, for sRGB we can use None and let the system handle it
                self.srgb_profile_bytes = None
        except:
            self.srgb_profile_bytes = None
    
    def normalize(self, img):
        """
        Converts image to sRGB color space with proper ICC profile handling.
        Uses perceptual rendering intent to preserve visual appearance.
        
        Args:
            img: PIL Image object
            
        Returns:
            Tuple of (PIL Image in sRGB color space, sRGB profile bytes or None)
        """
        if img is None:
            return None, None
            
        try:
            # Handle images with ICC profiles
            if "icc_profile" in img.info:
                src_profile_data = img.info["icc_profile"]
                
                try:
                    # Create profile object from embedded ICC data
                    src_profile_buffer = BytesIO(src_profile_data)
                    input_profile = ImageCms.ImageCmsProfile(src_profile_buffer)
                    
                    # Transform to sRGB using Perceptual Intent (0)
                    # Perceptual intent preserves visual relationships when converting
                    # from wide-gamut (Adobe RGB) to smaller gamut (sRGB)
                    # This prevents the "washed out" appearance
                    img = ImageCms.profileToProfile(
                        img,
                        input_profile,
                        self.srgb_profile,
                        renderingIntent=ImageCms.Intent.PERCEPTUAL,
                        outputMode='RGB'
                    )
                    
                    # After transformation, the image is in sRGB
                    # We can extract the sRGB profile from the transformed image
                    # or use the original sRGB profile bytes if available
                    return img, self.srgb_profile_bytes
                    
                except Exception as e:
                    print(f"⚠️ ICC profile transform failed: {e}. _bytesdard conversion.")
                    # Fallback to standard conversion
                    if img and img.mode != 'RGB':
                        img = img.convert('RGB')
                    return img if img else None, self.srgb_profile.tobytes() if img else None
            else:
                # No ICC profile present - convert mode if needed
                if img.mode == 'CMYK':
                    # CMYK without profile needs careful handling
                    # Use standard RGB conversion as fallback
                    print("⚠️ CMYK image without ICC profile - converting to RGB")
                    img = img.convert('RGB')
                elif img.mode not in ('RGB', 'L'):
                    # Handle RGBA, LA, P modes
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                
                return img, self.srgb_profile_bytes
                
        except Exception as e:
            print(f"⚠️ Color normalization error: {e}")
            # Emergency fallback
            if img and img.mode != 'RGB':
                img = img.convert('RGB')
            return img if img else None, None

def create_progress_bar(percentage):
    """Create a progress bar with the given percentage"""
    filled_blocks = int(percentage / 10)  # 10% per block
    empty_blocks = 10 - filled_blocks
    bar = "⬢" * filled_blocks + "⬡" * empty_blocks
    return f"[{bar}] {percentage}%"

async def convert_image_to_pdf(client, image_message, reply_message, pdf_filename=None, task_id=None):
    """Common function to convert image to PDF with compression"""
    downloaded_path = None
    pdf_path = None
    progress_msg = None
    
    # Generate task ID if not provided
    if not task_id:
        task_id = f"convert_{image_message.id}"
    
    # Register task for cancellation
    active_tasks[task_id] = {'cancelled': False, 'progress': 0}
    
    try:
        # Get the photo
        photo = image_message.photo
        # Get the file_id of the largest photo size (last in the list is largest)
        file_id = photo.file_id
        
        # Use 'Pdfio.pdf' as default filename if not provided
        if not pdf_filename:
            pdf_filename = "Pdfio.pdf"
        
        # Create cancel button
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_convert_{task_id}")]
        ])
        
        # Send initial progress message with cancel button
        progress_msg = await reply_message.reply_text(
            f"{create_progress_bar(0)}\n\nStatus: Downloading image...",
            reply_markup=cancel_keyboard
        )
        
        # Check for cancellation before download
        if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
            await progress_msg.edit_text("❌ Conversion cancelled by user.")
            return
        
        # Download the photo with timeout handling
        downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}.jpg")
        
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
            
            # Clean up temporary files immediately after upload
            # Use multiple attempts with delays if needed
            for attempt in range(3):
                try:
                    if downloaded_path and os.path.exists(downloaded_path):
                        os.remove(downloaded_path)
                        downloaded_path = None
                    break
                except:
                    if attempt < 2:
                        await asyncio.sleep(0.3)
            
            for attempt in range(3):
                try:
                    if pdf_path and os.path.exists(pdf_path):
                        os.remove(pdf_path)
                        pdf_path = None
                    break
                except:
                    if attempt < 2:
                        await asyncio.sleep(0.3)
            
            # Delete the progress message
            await progress_msg.delete()
            
            # Clean up task from active tasks
            if task_id in active_tasks:
                del active_tasks[task_id]
            
        else:
            await reply_message.reply_text("Failed to download the image.")
            if progress_msg:
                try:
                    await progress_msg.delete()
                except:
                    pass
    
    except TimeoutError:
        await reply_message.reply_text("Download timed out. Please try again with a smaller image.")
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