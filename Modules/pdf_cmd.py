"""PDF conversion command handler"""

from pyrogram.client import Client
from pyrogram.types import Message, CallbackQuery
from .core import convert_image_to_pdf, active_tasks

async def pdf_command_handler(client: Client, message: Message):
    """Handle /pdf command when user replies to an image"""
    # If this is a reply to an image, process it
    if message.reply_to_message and message.reply_to_message.photo:
        # Extract filename from command if provided
        command_parts = message.text.split(" ", 1)
        if len(command_parts) > 1:
            pdf_filename = command_parts[1].strip()
            # Ensure the filename ends with .pdf
            if not pdf_filename.lower().endswith('.pdf'):
                pdf_filename += '.pdf'
        else:
            pdf_filename = None  # Will generate unique name in convert_image_to_pdf function
        
        # Generate task ID for cancellation
        task_id = f"convert_{message.reply_to_message.id}"
        await convert_image_to_pdf(client, message.reply_to_message, message, pdf_filename, task_id)
    else:
        # If not replying to an image, explain the usage
        await message.reply_text(
            "Please reply to an image with /pdf command.\n\n"
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

# For backward compatibility - direct image handling is now managed in multipdf_cmd.py
# This function can be left empty or with a simple implementation if needed elsewhere
async def image_handler(client: Client, message: Message):
    """Handle direct image messages (for compatibility)"""
    # This function is now primarily handled in multipdf_cmd.py for collection purposes
    # If an image is sent directly without being in a collection process, 
    # we can notify the user about the multipdf feature
    user_id = message.from_user.id
    # Check if user is in the middle of a multipdf collection process
    from .multipdf_cmd import collected_images_store
    if user_id in collected_images_store and f"{user_id}_filename" in collected_images_store:
        # If in collection process, add to collection (this is handled by the multipdf handler)
        pass
    else:
        # If not in collection process, inform about the feature
        await message.reply_text(
            "📸 **New Feature Available!**\n\n"
            "Send images directly to collect them for a multi-image PDF.\n"
            "Then use `/multipdf` to start the collection process,\n"
            "`/done` to create the PDF, or `/cancel` to cancel."
        )