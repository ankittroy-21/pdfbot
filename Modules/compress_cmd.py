"""PDF compression command handler"""

import os
import asyncio
import subprocess
from pyrogram.client import Client
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    fitz = None
    HAS_PYMUPDF = False

try:
    import pikepdf
    HAS_PIKEPDF = True
except ImportError:
    pikepdf = None
    HAS_PIKEPDF = False

# Dictionary to track active compression tasks
active_tasks = {}

def create_progress_bar(percentage):
    """Create a progress bar with the given percentage"""
    filled_blocks = int(percentage / 10)  # 10% per block
    empty_blocks = 10 - filled_blocks
    bar = "⬢" * filled_blocks + "⬡" * empty_blocks
    return f"[{bar}] {percentage}%"

def estimate_compressed_size(original_size, power):
    """Estimate compressed file size based on power level"""
    # More accurate compression ratios based on testing
    ratios = {
        2: 0.40,  # Printer: ~60% reduction
        3: 0.25,  # eBook: ~75% reduction
        4: 0.15   # Screen: ~85% reduction (more conservative)
    }
    ratio = ratios.get(power, 0.40)
    return int(original_size * ratio)

async def hybrid_compress_pdf(input_path, output_path, power=3):
    """
    Hybrid 2-Stage Compression: Pikepdf (Structural) + Ghostscript/PyMuPDF (Content)
    
    :param power: 
        2: Printer (300dpi) - Good quality, ~50% reduction
        3: eBook (150dpi) - Best balance, ~70% reduction  
        4: Screen (72dpi) - Max compression, ~90% reduction
    :return: (success, original_size, compressed_size)
    """
    temp_structural = f"{input_path}_structural.tmp"
    temp_compressed = f"{input_path}_compressed.tmp"
    
    original_size = os.path.getsize(input_path)
    
    try:
        # STAGE 1: Structural Cleaning with pikepdf (Lossless)
        if HAS_PIKEPDF and pikepdf is not None:
            try:
                with pikepdf.open(input_path) as pdf:
                    pdf.remove_unreferenced_resources()
                    pdf.save(
                        temp_structural,
                        linearize=True,
                        compress_streams=True
                    )
                input_for_stage2 = temp_structural
            except:
                input_for_stage2 = input_path
        else:
            input_for_stage2 = input_path
        
        # STAGE 2: Content Compression with PyMuPDF
        if HAS_PYMUPDF and fitz is not None:
            doc = fitz.open(input_for_stage2)
            compressed_doc = fitz.open()
            
            # Improved scale factors - less aggressive to preserve quality
            scale_factors = {
                2: 0.85,  # Printer: 85% scale (minimal loss)
                3: 0.65,  # eBook: 65% scale (balanced)
                4: 0.50   # Screen: 50% scale (still readable)
            }
            scale = scale_factors.get(power, 0.65)
            
            # Better quality levels to preserve visual appearance
            quality_levels = {
                2: 50,  # Printer: High quality (minimal artifacts)
                3: 35,  # eBook: Good quality (balanced)
                4: 25   # Screen: Acceptable quality (readable, sharp text)
            }
            quality = quality_levels.get(power, 35)
            
            for page_num in range(len(doc)):
                # Check if task was cancelled
                task_id = f"{input_path}_task"
                if task_id in active_tasks and active_tasks[task_id].get('cancelled', False):
                    doc.close()
                    compressed_doc.close()
                    del doc, compressed_doc
                    return False, original_size, original_size
                
                page = doc[page_num]
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("jpeg", jpg_quality=quality)
                
                new_page = compressed_doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.insert_image(new_page.rect, stream=img_bytes)
            
            doc.close()
            del doc
            
            await asyncio.sleep(0.2)
            
            compressed_doc.save(
                temp_compressed,
                garbage=4,
                deflate=True,
                clean=True,
                pretty=False
            )
            compressed_doc.close()
            del compressed_doc
            
            await asyncio.sleep(0.2)
        else:
            return False, original_size, original_size
        
        # Check if compression was successful
        compressed_size = os.path.getsize(temp_compressed)
        
        if compressed_size < original_size:
            os.rename(temp_compressed, output_path)
            return True, original_size, compressed_size
        else:
            # Use structural-only if it's smaller
            if os.path.exists(temp_structural):
                structural_size = os.path.getsize(temp_structural)
                if structural_size < original_size:
                    os.rename(temp_structural, output_path)
                    return True, original_size, structural_size
            
            # Otherwise copy original
            import shutil
            shutil.copy2(input_path, output_path)
            return False, original_size, original_size
            
    finally:
        # Cleanup
        for temp_file in [temp_structural, temp_compressed]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

async def compress_command_handler(client: Client, message: Message):
    """Handle /compress command - show quality options"""
    # Check if the message is a reply to a document (PDF)
    if message.reply_to_message and message.reply_to_message.document:
        document = message.reply_to_message.document
        file_name = document.file_name
        
        # Check if the file is a PDF
        if file_name and (file_name.lower().endswith('.pdf') or document.mime_type == 'application/pdf'):
            # Get file size
            file_size = document.file_size
            
            # Estimate compressed sizes
            printer_size = estimate_compressed_size(file_size, 2)
            ebook_size = estimate_compressed_size(file_size, 3)
            screen_size = estimate_compressed_size(file_size, 4)
            
            # Generate unique task ID
            import time
            task_id = f"{message.from_user.id}_{int(time.time())}"
            
            # Create inline keyboard with 3 quality options
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"🖨️ High Quality (~{printer_size/1024:.0f} KB)",
                    callback_data=f"compress_2_{message.reply_to_message.id}_{task_id}"
                )],
                [InlineKeyboardButton(
                    f"⚖️ Balanced (~{ebook_size/1024:.0f} KB)",
                    callback_data=f"compress_3_{message.reply_to_message.id}_{task_id}"
                )],
                [InlineKeyboardButton(
                    f"📉 Max Compression (~{screen_size/1024:.0f} KB)",
                    callback_data=f"compress_4_{message.reply_to_message.id}_{task_id}"
                )]
            ])
            
            await message.reply_text(
                f"📄 **PDF Compression Options**\n\n"
                f"Original size: {file_size/1024:.1f} KB\n\n"
                f"Choose compression level:",
                reply_markup=keyboard
            )
        else:
            await message.reply_text("Please reply to a PDF file with /compress command.")
    else:
        await message.reply_text(
            "Please reply to a PDF file with /compress command.\n\n"
            "Usage:\n"
            "- Reply to a PDF with /compress to see compression options"
        )

async def handle_compression_callback(client: Client, callback_query: CallbackQuery):
    """Handle compression quality button callbacks"""
    # Convert data to string if it's bytes
    data_raw = callback_query.data
    if isinstance(data_raw, bytes):
        data = data_raw.decode('utf-8')
    else:
        data = str(data_raw)
    
    # Handle cancellation
    if data.startswith("cancel_compress_"):
        task_id = data.replace("cancel_compress_", "")
        if task_id in active_tasks:
            active_tasks[task_id]['cancelled'] = True
            await callback_query.answer("✅ Compression cancelled!", show_alert=True)
            try:
                await callback_query.message.edit_text("❌ Compression cancelled by user.")
            except:
                pass
        return
    
    parts = data.split("_")
    
    if len(parts) < 3 or parts[0] != "compress":
        return
    
    power = int(parts[1])  # 2, 3, or 4
    message_id = int(parts[2])
    task_id = parts[3] if len(parts) > 3 else "unknown"
    
    # Get the original message
    try:
        original_message_result = await client.get_messages(
            callback_query.message.chat.id,
            message_id
        )
        # Handle both single message and list return
        if isinstance(original_message_result, list):
            if len(original_message_result) == 0:
                await callback_query.answer("Original message not found!", show_alert=True)
                return
            original_message = original_message_result[0]
        else:
            original_message = original_message_result
    except:
        await callback_query.answer("Original message not found!", show_alert=True)
        return
    
    if not original_message.document:
        await callback_query.answer("Document not found!", show_alert=True)
        return
    
    # Answer callback to remove loading state
    quality_names = {2: "High Quality", 3: "Balanced", 4: "Max Compression"}
    await callback_query.answer(f"Compressing with {quality_names[power]}...")
    
    # Start compression
    await perform_compression(client, callback_query.message, original_message, power, task_id)
async def perform_compression(client: Client, reply_to_message: Message, original_pdf_message: Message, power: int, task_id: str):
    """Perform the actual compression"""
    downloaded_path = None
    compressed_pdf_path = None
    progress_msg = None
    
    # Register task
    active_tasks[task_id] = {'cancelled': False, 'progress': 0}
    
    try:
        document = original_pdf_message.document
        file_name = document.file_name
        
        # Generate output filename
        quality_names = {2: "HQ", 3: "Balanced", 4: "MaxComp"}
        compressed_pdf_filename = f"Compressed_{quality_names[power]}_{file_name}"
        
        # Create cancel button
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_compress_{task_id}")]
        ])
        
        # Send initial progress message with cancel button
        progress_msg = await reply_to_message.edit_text(
            f"{create_progress_bar(0)}\n\nStatus: Downloading PDF...",
            reply_markup=cancel_keyboard
        )
        
        # Download the PDF
        downloaded_result = await client.download_media(document.file_id, file_name=f"temp_{document.file_id}.pdf")
        
        if downloaded_result and isinstance(downloaded_result, str):
            downloaded_path = downloaded_result
            
            # Check if cancelled
            if active_tasks[task_id]['cancelled']:
                await reply_to_message.edit_text("❌ Compression cancelled by user.")
                if os.path.exists(downloaded_path):
                    os.remove(downloaded_path)
                return
            
            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_compress_{task_id}")]
            ])
            await progress_msg.edit_text(
                f"{create_progress_bar(30)}\n\nStatus: Compressing PDF...",
                reply_markup=cancel_keyboard
            )
            
            # Perform hybrid compression
            compressed_pdf_path = compressed_pdf_filename
            
            # Store task info for cancellation checking
            active_tasks[task_id]['download_path'] = downloaded_path
            success, original_size, compressed_size = await hybrid_compress_pdf(
                downloaded_path,
                compressed_pdf_path,
                power=power
            )
            
            if not success:
                await reply_to_message.edit_text("⚠️ Compression did not reduce file size. Sending original.")
                await reply_to_message.reply_document(downloaded_path, caption=f"Original: {file_name}")
                # Cleanup
                for attempt in range(5):
                    try:
                        if downloaded_path and os.path.exists(downloaded_path):
                            os.remove(downloaded_path)
                        break
                    except:
                        if attempt < 4:
                            await asyncio.sleep(0.5)
                return
            
            # Upload compressed PDF
            await progress_msg.edit_text(f"{create_progress_bar(80)}\n\nStatus: Uploading compressed PDF...")
            
            size_reduction = round(((original_size - compressed_size) / original_size) * 100, 2)
            quality_names = {2: "High Quality", 3: "Balanced", 4: "Max Compression"}
            
            caption = (f"✅ **Compressed - {quality_names[power]}**\n\n"
                      f"📊 Original: {original_size/1024:.1f} KB\n"
                      f"📉 Compressed: {compressed_size/1024:.1f} KB\n"
                      f"💾 Saved: {size_reduction}%")
            
            await reply_to_message.reply_document(compressed_pdf_path, caption=caption)
            
            # Wait and cleanup
            await asyncio.sleep(0.5)
            
            for attempt in range(5):
                try:
                    if downloaded_path and os.path.exists(downloaded_path):
                        os.remove(downloaded_path)
                    break
                except:
                    if attempt < 4:
                        await asyncio.sleep(0.5)
            
            for attempt in range(5):
                try:
                    if compressed_pdf_path and os.path.exists(compressed_pdf_path):
                        os.remove(compressed_pdf_path)
                    break
                except:
                    if attempt < 4:
                        await asyncio.sleep(0.5)
            
            # Delete progress message
            try:
                await progress_msg.delete()
            except:
                pass
        else:
            await reply_to_message.edit_text("❌ Failed to download PDF")
    
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        try:
            await reply_to_message.edit_text(error_msg)
        except:
            await reply_to_message.reply_text(error_msg)
        
        # Cleanup on error
        for attempt in range(5):
            try:
                if downloaded_path and os.path.exists(downloaded_path):
                    os.remove(downloaded_path)
                break
            except:
                if attempt < 4:
                    await asyncio.sleep(0.5)
        
        for attempt in range(5):
            try:
                if compressed_pdf_path and os.path.exists(compressed_pdf_path):
                    os.remove(compressed_pdf_path)
                break
            except:
                if attempt < 4:
                    await asyncio.sleep(0.5)
    
    finally:
        # Always remove task from active tasks
        if task_id in active_tasks:
            del active_tasks[task_id]