"""Register all command handlers"""

from pyrogram import filters
from pyrogram.handlers.message_handler import MessageHandler
from pyrogram.handlers.callback_query_handler import CallbackQueryHandler
from .start_cmd import start_command, help_command
from .pdf_cmd import pdf_command_handler, handle_convert_callback
from .compress_cmd import compress_command_handler, handle_compression_callback
from .multipdf_cmd import (
    multipdf_command_handler,
    collect_image_handler,
    done_command_handler,
    cancel_command_handler,
    multipdf_callback_handler,
    handle_multipdf_cancel
)
from .image_file_handler import image_file_handler, is_valid_image_file

# Custom filter for image documents
async def image_document_filter(_, __, message):
    return await is_valid_image_file(message)

image_doc_filter = filters.create(image_document_filter)

def register(app):
    """Register all handlers with the application"""
    # Register basic commands
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(help_command, filters.command("help")))
    
    # Register PDF conversion commands
    app.add_handler(MessageHandler(pdf_command_handler, filters.command("pdf")))
    
    # Register multi-PDF commands
    app.add_handler(MessageHandler(multipdf_command_handler, filters.command("multipdf")))
    app.add_handler(MessageHandler(done_command_handler, filters.command("done")))
    app.add_handler(MessageHandler(cancel_command_handler, filters.command("cancel")))
    
    # Register photo handler for multi-PDF collection (must be after commands)
    app.add_handler(MessageHandler(collect_image_handler, filters.photo))
    
    # Register document handler for image files in multi-PDF collection (only processes if session active)
    app.add_handler(MessageHandler(collect_image_handler, filters.document & image_doc_filter))
    
    # Register document handler for image files (when using /pdf command with image document)
    app.add_handler(MessageHandler(image_file_handler, filters.command("pdf") & filters.document))
    
    # Register PDF compression command
    app.add_handler(MessageHandler(compress_command_handler, filters.command("compress")))
    
    # Register compression callback handler - include cancel callbacks too
    app.add_handler(CallbackQueryHandler(handle_compression_callback, filters.regex(r"^(compress_|cancel_compress_)")))
    
    # Register conversion callback handler for cancel buttons
    app.add_handler(CallbackQueryHandler(handle_convert_callback, filters.regex(r"^cancel_convert_")))
    
    # Register multi-PDF callback handlers
    app.add_handler(CallbackQueryHandler(multipdf_callback_handler, filters.regex(r"^multipdf_(done|a4|auto)_")))
    app.add_handler(CallbackQueryHandler(handle_multipdf_cancel, filters.regex(r"^cancel_multipdf_(selection|collection)_")))
    
    # Note: Auto-conversion removed - users must use /pdf command