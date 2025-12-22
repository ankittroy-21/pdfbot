"""PDF conversion command handler"""

import os
from pyrogram.client import Client
from pyrogram.types import Message, CallbackQuery
from .core import convert_image_to_pdf, active_tasks
from .rate_limiter import pdf_rate_limiter

async def pdf_command_handler(client: Client, message: Message):
    """Handle /pdf command when user replies to an image"""
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
    
    # If this is a reply to an image (photo or document), process it
    if message.reply_to_message:
        # Handle photo messages
        if message.reply_to_message.photo:
            # Extract filename from command if provided
            command_parts = message.text.split(" ", 1)
            if len(command_parts) > 1:
                pdf_filename = command_parts[1].strip()
                # Ensure the filename ends with .pdf
                if not pdf_filename.lower().endswith('.pdf'):
                    pdf_filename += '.pdf'
            else:
                pdf_filename = None # Will generate unique name in convert_image_to_pdf function
             
            # Generate task ID for cancellation
            task_id = f"convert_{message.reply_to_message.id}"
            await convert_image_to_pdf(client, message.reply_to_message, message, pdf_filename, task_id)
        # Handle document messages that are valid images
        elif message.reply_to_message.document:
            from .image_file_handler import is_valid_image_file
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
                        pdf_filename = None  # Will generate unique name in convert_image_to_pdf function
                 
                # Generate task ID for cancellation
                task_id = f"convert_doc_{message.reply_to_message.id}"
                from .image_file_handler import convert_image_file_to_pdf
                await convert_image_file_to_pdf(client, message.reply_to_message, message, pdf_filename, task_id)
            else:
                # Not an image document, explain the usage
                await message.reply_text(
                    "Please reply to an image with /pdf command.\n\n"
                    "Supported formats: JPG, PNG, BMP, WEBP, TIFF, GIF, and others.\n\n"
                    "Usage:\n"
                    "- Reply to an image with /pdf to convert with unique name\n"
                    "- Use /pdf filename to specify a custom name for the PDF"
                )
        else:
            # If not replying to an image, explain the usage
            await message.reply_text(
                "Please reply to an image with /pdf command.\n\n"
                "Supported formats: JPG, PNG, BMP, WEBP, TIFF, GIF, and others.\n\n"
                "Usage:\n"
                "- Reply to an image with /pdf to convert with unique name\n"
                "- Use /pdf filename to specify a custom name for the PDF"
            )

async def handle_convert_callback(client: Client, callback_query: CallbackQuery):
    """Handle conversion cancel button clicks"""
    data_raw = callback_query.data
    
    # Handle both string and bytes
    if isinstance(data_raw, bytes):
        data = data_raw.decode('utf-8')
    else:
        data = str(data_raw)
    
    # Handle cancellation
    if data.startswith("cancel_convert_"):
        task_id = data.replace("cancel_convert_", "")
        if task_id in active_tasks:
            active_tasks[task_id]['cancelled'] = True
            await callback_query.answer("✅ Conversion cancelled!", show_alert=True)
            try:
                await callback_query.message.edit_text("❌ Conversion cancelled by user.")
            except:
                pass


