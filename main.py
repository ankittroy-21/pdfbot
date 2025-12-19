import os
import asyncio
from pyrogram.client import Client
from pyrogram import filters
from config import API_ID, API_HASH, BOT_TOKEN
from Modules.register import register
from Modules.async_file_handler import AsyncFileHandler

# Initialize the bot client
app = Client(
    "pdf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=1  # Reduce sleep threshold to handle API calls more efficiently
)

# Register handlers
register(app)

# Background cleanup task
async def periodic_cleanup():
    """Periodically clean up temporary files to prevent disk space issues"""
    while True:
        try:
            # Wait 30 minutes between cleanups
            await asyncio.sleep(1800)
            
            print("🧹 Starting periodic cleanup...")
            
            # Clean up temp files in downloads directory
            count = await AsyncFileHandler.cleanup_directory("downloads", "temp_*.jpg")
            count += await AsyncFileHandler.cleanup_directory("downloads", "temp_*.pdf")
            count += await AsyncFileHandler.cleanup_directory("downloads", "*.jpg")
            count += await AsyncFileHandler.cleanup_directory("downloads", "*.pdf")
            
            # Clean up orphaned temp_sessions folders
            import shutil
            temp_sessions_path = "downloads/temp_sessions"
            if os.path.exists(temp_sessions_path):
                for session_folder in os.listdir(temp_sessions_path):
                    folder_path = os.path.join(temp_sessions_path, session_folder)
                    if os.path.isdir(folder_path):
                        try:
                            shutil.rmtree(folder_path, ignore_errors=True)
                            count += 1
                            print(f"🗑️ Removed orphaned session folder: {session_folder}")
                        except Exception as e:
                            print(f"⚠️ Could not remove {session_folder}: {e}")
            
            if count > 0:
                print(f"✅ Cleanup complete: {count} files/folders removed")
            else:
                print("✅ Cleanup complete: No temp files found")
                
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

if __name__ == "__main__":
    print("🤖 Bot has started!")
    # Start cleanup task in background
    loop = asyncio.get_event_loop()
    cleanup_task = loop.create_task(periodic_cleanup())
    
    try:
        app.run()
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print("\nIf you're seeing a SESSION_REVOKED error:")
        print("1. Check if you've terminated all other Telegram sessions from @BotFather")
        print("2. Delete the pdf_bot.session file in this directory")
        print("3. Restart the bot")
        print("\nIf you're seeing a CONNECTION_FAILED error:")
        print("1. Check your internet connection")
        print("2. Make sure your API credentials are correct")
        print("3. Verify that your bot token is valid")
    finally:
        # Cancel cleanup task on shutdown
        cleanup_task.cancel()
        try:
            loop.run_until_complete(cleanup_task)
        except asyncio.CancelledError:
            print("🛑 Cleanup task stopped")