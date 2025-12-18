"""Supabase client for user tracking and persistent session storage"""

import os
import time
from typing import Optional, List, Dict
from config import USE_SUPABASE, SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client if enabled
supabase_client = None
if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        if SUPABASE_URL and SUPABASE_KEY:
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase connected successfully!")
        else:
            print("⚠️ Supabase URL or KEY is missing")
            USE_SUPABASE = False
    except Exception as e:
        print(f"⚠️ Supabase connection failed: {e}")
        print("📝 Falling back to in-memory storage")
        USE_SUPABASE = False
else:
    print("📝 Using in-memory storage (Supabase not configured)")

# In-memory fallback storage (used when Supabase is disabled)
_memory_store = {}


class UserTracker:
    """Track user activity to prevent spam"""
    
    @staticmethod
    async def track_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None):
        """Record or update user information"""
        if USE_SUPABASE and supabase_client:
            try:
                # Check if user exists
                result = supabase_client.table('users')\
                    .select('user_id')\
                    .eq('user_id', user_id)\
                    .execute()
                
                current_time = int(time.time())
                
                if result.data:
                    # Update existing user
                    supabase_client.table('users')\
                        .update({
                            'username': username,
                            'first_name': first_name,
                            'last_name': last_name,
                            'last_active': current_time
                        })\
                        .eq('user_id', user_id)\
                        .execute()
                else:
                    # Insert new user
                    supabase_client.table('users').insert({
                        'user_id': user_id,
                        'username': username,
                        'first_name': first_name,
                        'last_name': last_name,
                        'join_date': current_time,
                        'last_active': current_time,
                        'total_pdfs_created': 0
                    }).execute()
            except Exception as e:
                print(f"⚠️ User tracking failed: {e}")
    
    @staticmethod
    async def increment_pdf_count(user_id: int):
        """Increment total PDFs created by user"""
        if USE_SUPABASE and supabase_client:
            try:
                # Get current count
                result = supabase_client.table('users')\
                    .select('total_pdfs_created')\
                    .eq('user_id', user_id)\
                    .execute()
                
                if result.data:
                    current_count = result.data[0].get('total_pdfs_created', 0)
                    supabase_client.table('users')\
                        .update({'total_pdfs_created': current_count + 1})\
                        .eq('user_id', user_id)\
                        .execute()
            except Exception as e:
                print(f"⚠️ PDF count update failed: {e}")
    
    @staticmethod
    async def get_user_stats(user_id: int) -> Optional[Dict]:
        """Get user statistics"""
        if USE_SUPABASE and supabase_client:
            try:
                result = supabase_client.table('users')\
                    .select('*')\
                    .eq('user_id', user_id)\
                    .execute()
                return result.data[0] if result.data else None
            except Exception as e:
                print(f"⚠️ Get user stats failed: {e}")
                return None
        return None


class SupabaseStorage:
    """Session storage with automatic cleanup - images persist until PDF is created"""
    
    @staticmethod
    async def create_session(user_id: int) -> str:
        """Create a new multipdf session"""
        session_id = f"{user_id}_{int(time.time())}"
        current_time = int(time.time())
        
        if USE_SUPABASE and supabase_client:
            try:
                # Store session metadata in Supabase
                supabase_client.table('multipdf_sessions').insert({
                    'session_id': session_id,
                    'user_id': user_id,
                    'status': 'collecting',
                    'created_at': current_time,
                    'updated_at': current_time
                }).execute()
            except Exception as e:
                print(f"⚠️ Supabase session creation failed: {e}")
                # Fall back to memory
                _memory_store[f"session_{session_id}"] = {
                    'user_id': user_id,
                    'status': 'collecting',
                    'images': [],
                    'created_at': current_time
                }
        else:
            # Use memory storage
            _memory_store[f"session_{session_id}"] = {
                'user_id': user_id,
                'status': 'collecting',
                'images': [],
                'created_at': current_time
            }
        
        return session_id
    
    @staticmethod
    async def add_image(session_id: str, image_path: str, order: int) -> bool:
        """Add an image to session - uploads to Supabase Storage"""
        if USE_SUPABASE and supabase_client:
            try:
                # Upload image to Supabase Storage
                with open(image_path, 'rb') as f:
                    storage_path = f"sessions/{session_id}/{order}.jpg"
                    supabase_client.storage.from_('images').upload(
                        storage_path,
                        f,
                        file_options={"content-type": "image/jpeg"}
                    )
                
                # Record in database
                supabase_client.table('session_images').insert({
                    'session_id': session_id,
                    'image_path': storage_path,
                    'image_order': order,
                    'created_at': int(time.time())
                }).execute()
                
                return True
            except Exception as e:
                print(f"⚠️ Supabase image upload failed: {e}")
                # Fall back to memory
                if f"session_{session_id}" in _memory_store:
                    _memory_store[f"session_{session_id}"]['images'].append(image_path)
                return True
        else:
            # Use memory storage
            if f"session_{session_id}" in _memory_store:
                _memory_store[f"session_{session_id}"]['images'].append(image_path)
            return True
    
    @staticmethod
    async def get_session_images(session_id: str) -> List[str]:
        """Get all images for a session - downloads from Supabase if needed"""
        if USE_SUPABASE and supabase_client:
            try:
                # Get image records from database
                result = supabase_client.table('session_images')\
                    .select('image_path')\
                    .eq('session_id', session_id)\
                    .order('image_order')\
                    .execute()
                
                if not result.data:
                    # Fall back to memory if no data in Supabase
                    if f"session_{session_id}" in _memory_store:
                        return _memory_store[f"session_{session_id}"]['images']
                    return []
                
                # Download images from Supabase Storage to user-specific temp folder
                local_paths = []
                session_temp_folder = f"downloads/temp_sessions/{session_id}"
                os.makedirs(session_temp_folder, exist_ok=True)
                
                for img in result.data:
                    storage_path = img['image_path']
                    
                    # Download from Supabase Storage
                    file_data = supabase_client.storage.from_('images').download(storage_path)
                    
                    # Save to user-specific temp file
                    local_path = f"{session_temp_folder}/image_{len(local_paths)}.jpg"
                    with open(local_path, 'wb') as f:
                        f.write(file_data)
                    
                    local_paths.append(local_path)
                
                return local_paths
            except Exception as e:
                print(f"⚠️ Supabase image download failed: {e}")
                # Fall back to memory
                if f"session_{session_id}" in _memory_store:
                    return _memory_store[f"session_{session_id}"]['images']
                return []
        else:
            # Use memory storage
            if f"session_{session_id}" in _memory_store:
                return _memory_store[f"session_{session_id}"]['images']
            return []
    
    @staticmethod
    async def get_session(session_id: str) -> Optional[Dict]:
        """Get session details"""
        if USE_SUPABASE and supabase_client:
            try:
                result = supabase_client.table('multipdf_sessions')\
                    .select('*')\
                    .eq('session_id', session_id)\
                    .execute()
                return result.data[0] if result.data else None
            except Exception as e:
                print(f"⚠️ Supabase query failed: {e}")
                return _memory_store.get(f"session_{session_id}")
        else:
            return _memory_store.get(f"session_{session_id}")
    
    @staticmethod
    async def update_session_status(session_id: str, status: str):
        """Update session status and refresh timestamp"""
        if USE_SUPABASE and supabase_client:
            try:
                # Always update timestamp to extend the session
                supabase_client.table('multipdf_sessions')\
                    .update({
                        'status': status, 
                        'updated_at': int(time.time()),
                        'created_at': int(time.time())  # Refresh the timer
                    })\
                    .eq('session_id', session_id)\
                    .execute()
            except Exception as e:
                print(f"⚠️ Supabase status update failed: {e}")
        
        # Also update memory if exists
        if f"session_{session_id}" in _memory_store:
            _memory_store[f"session_{session_id}"]['status'] = status
            _memory_store[f"session_{session_id}"]['created_at'] = int(time.time())
    
    @staticmethod
    async def delete_session(session_id: str):
        """Delete session completely - removes from Supabase Storage and database"""
        if USE_SUPABASE and supabase_client:
            try:
                # Step 1: Get all image records
                result = supabase_client.table('session_images')\
                    .select('image_path')\
                    .eq('session_id', session_id)\
                    .execute()
                
                # Step 2: Delete each image from Supabase Storage
                deleted_storage_count = 0
                for img in result.data:
                    try:
                        supabase_client.storage.from_('images').remove([img['image_path']])
                        deleted_storage_count += 1
                    except Exception as e:
                        print(f"⚠️ Failed to delete storage file {img['image_path']}: {e}")
                
                if deleted_storage_count > 0:
                    print(f"🗑️ Deleted {deleted_storage_count} file(s) from Supabase Storage")
                
                # Step 3: Delete session record (CASCADE will delete session_images)
                delete_result = supabase_client.table('multipdf_sessions')\
                    .delete()\
                    .eq('session_id', session_id)\
                    .execute()
                
                print(f"✅ Session {session_id} deleted from Supabase")
            except Exception as e:
                print(f"⚠️ Supabase cleanup failed for {session_id}: {e}")
        
        # Remove from memory
        _memory_store.pop(f"session_{session_id}", None)
    
    @staticmethod
    async def cleanup_old_sessions(max_age_seconds: int = 1800):
        """Clean up old sessions (30+ min) and ALL completed sessions"""
        current_time = time.time()
        
        if USE_SUPABASE and supabase_client:
            try:
                # Step 1: Delete ALL completed sessions (no longer needed)
                completed_result = supabase_client.table('multipdf_sessions')\
                    .delete()\
                    .eq('status', 'completed')\
                    .execute()
                
                # Step 2: Find and delete old active sessions (30+ min)
                result = supabase_client.table('multipdf_sessions')\
                    .select('session_id, created_at')\
                    .neq('status', 'completed')\
                    .execute()
                
                deleted_count = 0
                for session in result.data:
                    if not isinstance(session, dict):
                        continue
                    
                    created_at = session.get('created_at', current_time)
                    session_id = session.get('session_id', '')
                    
                    # Convert to float safely
                    try:
                        if isinstance(created_at, (int, float)):
                            created_at_float = float(created_at)
                        elif isinstance(created_at, str):
                            created_at_float = float(created_at)
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                    
                    # Delete old sessions (30+ min old)
                    if session_id and (current_time - created_at_float) > max_age_seconds:
                        await SupabaseStorage.delete_session(str(session_id))
                        deleted_count += 1
                
                if deleted_count > 0:
                    print(f"🧹 Cleaned up {deleted_count} old session(s)")
            except Exception as e:
                print(f"⚠️ Cleanup failed: {e}")
        
        # Also clean memory store
        to_delete = []
        for key in _memory_store.keys():
            if key.startswith('session_'):
                session = _memory_store[key]
                created_at = session.get('created_at', current_time)
                if (current_time - created_at) > max_age_seconds:
                    to_delete.append(key)
        
        for key in to_delete:
            _memory_store.pop(key, None)
    
    @staticmethod
    async def get_user_session(user_id: int) -> Optional[str]:
        """Get active session ID for a user"""
        if USE_SUPABASE and supabase_client:
            try:
                result = supabase_client.table('multipdf_sessions')\
                    .select('session_id')\
                    .eq('user_id', user_id)\
                    .in_('status', ['collecting', 'awaiting_selection'])\
                    .order('created_at', desc=True)\
                    .limit(1)\
                    .execute()
                return result.data[0]['session_id'] if result.data else None
            except Exception as e:
                print(f"⚠️ Supabase query failed: {e}")
        
        # Fall back to memory
        for key, session in _memory_store.items():
            if key.startswith('session_') and session.get('user_id') == user_id:
                if session.get('status') in ['collecting', 'awaiting_selection']:
                    return key.replace('session_', '')
        return None
