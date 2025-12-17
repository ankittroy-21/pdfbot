"""Core functionality shared across commands"""

from PIL import Image
from io import BytesIO
import os
import asyncio
import fitz  # PyMuPDF

def create_progress_bar(percentage):
    """Create a progress bar with the given percentage"""
    filled_blocks = int(percentage / 10)  # 10% per block
    empty_blocks = 10 - filled_blocks
    bar = "⬢" * filled_blocks + "⬡" * empty_blocks
    return f"[{bar}] {percentage}%"

async def convert_image_to_pdf(client, image_message, reply_message, pdf_filename=None):
    """Common function to convert image to PDF with compression"""
    downloaded_path = None
    pdf_path = None
    progress_msg = None
    
    try:
        # Get the photo
        photo = image_message.photo
        # Get the file_id of the largest photo size (last in the list is largest)
        file_id = photo.file_id
        
        # Use 'Pdfio.pdf' as default filename if not provided
        if not pdf_filename:
            pdf_filename = "Pdfio.pdf"
        
        # Send initial progress message
        progress_msg = await reply_message.reply_text(f"{create_progress_bar(0)}\n\nStatus: Downloading image...")
        
        # Download the photo with timeout handling
        downloaded_result = await client.download_media(file_id, file_name=f"temp_{file_id}.jpg")
        
        # Make sure download was successful and it's a string path
        if downloaded_result and isinstance(downloaded_result, str):
            downloaded_path = downloaded_result
            # Update progress to converting
            await progress_msg.edit_text(f"{create_progress_bar(30)}\n\nStatus: Converting to PDF...")
            
            # Convert image to PDF with advanced optimization
            img = Image.open(downloaded_path)
            
            # Optimize the image before creating PDF
            if img.mode in ('RGBA', 'LA', 'P'):
                # Convert to RGB if the image has transparency
                img = img.convert('RGB')
            
            # Do NOT resize initially - we'll handle it in PDF compression
            
            # Create PDF using optimized settings
            pdf_path = pdf_filename  # Use the provided filename
            
            # Use PyMuPDF for maximum compression with aggressive optimization
            if fitz is not None:
                # First, aggressively compress the source image before PDF conversion
                temp_img_path = f"temp_{file_id}_for_pdf.jpg"
                
                # Calculate target dimensions (reduce to max 1200px on longest side for compression)
                max_dimension = 1200
                width, height = img.size
                if width > max_dimension or height > max_dimension:
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save with aggressive JPEG compression (quality=25 for ~80KB target)
                img.save(temp_img_path, "JPEG", quality=25, optimize=True, progressive=True)
                
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
                
                # Apply aggressive post-processing compression
                try:
                    await asyncio.sleep(0.1)
                    
                    # Use Ghostscript-style compression via PyMuPDF
                    final_doc = fitz.open(pdf_path)
                    
                    # Create a new document for recompressed output
                    compressed_doc = fitz.open()
                    
                    for page_num in range(len(final_doc)):
                        page = final_doc[page_num]
                        
                        # Get page as pixmap with reduced DPI (72 DPI for screen quality)
                        mat = fitz.Matrix(0.5, 0.5)  # Scale down to 50% for more compression
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        
                        # Convert pixmap to JPEG bytes with low quality
                        img_bytes = pix.tobytes("jpeg", jpg_quality=20)
                        
                        # Create new page in compressed doc
                        new_page = compressed_doc.new_page(width=page.rect.width, height=page.rect.height)
                        
                        # Insert the compressed image
                        new_page.insert_image(new_page.rect, stream=img_bytes)
                    
                    final_doc.close()
                    
                    # Save the heavily compressed version
                    compressed_doc.save(pdf_path,
                                       garbage=4,
                                       deflate=True,
                                       clean=True,
                                       pretty=False)
                    compressed_doc.close()
                    
                    del final_doc, compressed_doc
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    # If advanced compression fails, keep the basic compressed version
                    pass
            else:
                # Fallback to PIL with aggressive compression
                # Resize for compression
                max_dimension = 1200
                width, height = img.size
                if width > max_dimension or height > max_dimension:
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                img.save(pdf_path, "PDF",
                         resolution=72.0,           # Screen resolution for smaller size
                         save_all=True,
                         optimize=True,
                         quality=30)                # Low quality for aggressive compression
            
            # Update progress to uploading
            await progress_msg.edit_text(f"{create_progress_bar(70)}\n\nStatus: Uploading PDF...")
            
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
    except Exception as e:
        await reply_message.reply_text(f"An error occurred: {str(e)}")
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