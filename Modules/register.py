"""Register all command handlers"""

from pyrogram import filters
from pyrogram.handlers.message_handler import MessageHandler
from pyrogram.handlers.callback_query_handler import CallbackQueryHandler
from .start_cmd import start_command, help_command
from .pdf_cmd import pdf_command_handler
from .compress_cmd import compress_command_handler, handle_compression_callback

def register(app):
    """Register all handlers with the application"""
    # Register basic commands
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(help_command, filters.command("help")))
    
    # Register PDF conversion commands
    app.add_handler(MessageHandler(pdf_command_handler, filters.command("pdf")))
    
    # Register PDF compression command
    app.add_handler(MessageHandler(compress_command_handler, filters.command("compress")))
    
    # Register compression callback handler
    app.add_handler(CallbackQueryHandler(handle_compression_callback, filters.regex(r"^compress_")))
    
    # Note: Auto-conversion removed - users must use /pdf command