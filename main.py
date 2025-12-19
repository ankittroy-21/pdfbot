import os
import asyncio
from pyrogram.client import Client
from pyrogram import filters
from config import API_ID, API_HASH, BOT_TOKEN, REDIS_URL
from Modules.register import register
from Modules.async_file_handler import AsyncFileHandler
from Modules.redis_session import RedisSessionStorage
from Modules.health_check import HealthCheckServer
from Modules.session_adapter import SessionStorageAdapter
from Modules.supabase_client import SupabaseStorage

# Initialize the bot client
app = Client(
    "pdf_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=1  # Reduce sleep threshold to handle API calls more efficiently
)

# Initialize Redis session storage (optional)
redis_storage = RedisSessionStorage(REDIS_URL)

# Initialize session adapter (Redis preferred, Supabase fallback)
session_storage = SessionStorageAdapter(redis_storage, SupabaseStorage)

# Set session storage in multipdf handler
from Modules import multipdf_cmd
multipdf_cmd.set_session_storage(session_storage)

# Initialize health check server
health_server = HealthCheckServer(app, redis_storage, port=8080)

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
    print("⚡ Phase 1 Optimizations Active:")
    print("  ✅ Async file operations")
    print("  ✅ Rate limiting (10 PDFs/min, 5 compressions/min, 3 multi-PDFs/2min)")
    print("  ✅ Automatic cleanup every 30 minutes")
    
    # Get event loop
    loop = asyncio.get_event_loop()
    
    # Start Redis connection
    loop.run_until_complete(redis_storage.connect())
    
    # Start health check server
    loop.run_until_complete(health_server.start())
    
    # Start cleanup task in background
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
        # Cleanup tasks on shutdown
        print("\n🛑 Shutting down...")
        
        # Cancel cleanup task
        cleanup_task.cancel()
        try:
            loop.run_until_complete(cleanup_task)
        except asyncio.CancelledError:
            print("  ✅ Cleanup task stopped")
        
        # Stop health server
        loop.run_until_complete(health_server.stop())
        
        # Disconnect Redis
        loop.run_until_complete(redis_storage.disconnect())
        
        print("👋 Goodbye!")