"""
Session Storage Adapter
Provides unified interface for session storage with Redis (preferred) and Supabase (fallback)
"""

from typing import Optional, List, Dict, Any


class SessionStorageAdapter:
    """
    Adapter that uses Redis if available, falls back to Supabase otherwise.
    Provides a unified interface for session management.
    """
    
    def __init__(self, redis_storage=None, supabase_storage=None):
        """
        Initialize the adapter with Redis and/or Supabase storage.
        
        Args:
            redis_storage: RedisSessionStorage instance (optional)
            supabase_storage: SupabaseStorage instance (optional)
        """
        self.redis = redis_storage
        self.supabase = supabase_storage
        
        # Determine which storage to use
        self._use_redis = redis_storage and redis_storage.is_enabled
        
        if self._use_redis:
            print("✅ Using Redis for session storage (distributed)")
        elif self.supabase:
            print("✅ Using Supabase for session storage (fallback)")
        else:
            print("⚠️ No session storage configured - using in-memory (not persistent)")
    
    @property
    def storage_type(self) -> str:
        """Get the active storage type"""
        if self._use_redis:
            return "redis"
        elif self.supabase:
            return "supabase"
        else:
            return "memory"
    
    async def create_session(self, user_id: int, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Create a new session"""
        if self._use_redis:
            return await self.redis.create_session(user_id, metadata)  # type: ignore
        elif self.supabase:
            return await self.supabase.create_session(user_id)
        return None
    
    async def get_user_session(self, user_id: int) -> Optional[str]:
        """Get active session for user"""
        if self._use_redis:
            return await self.redis.get_user_session(user_id)  # type: ignore
        elif self.supabase:
            return await self.supabase.get_user_session(user_id)
        return None
    
    async def add_image(self, session_id: str, image_path: str, order: int) -> bool:
        """Add image to session"""
        if self._use_redis:
            return await self.redis.add_image(session_id, image_path, order)  # type: ignore
        elif self.supabase:
            return await self.supabase.add_image(session_id, image_path, order)
        return False
    
    async def get_session_images(self, session_id: str) -> List[str]:
        """Get all images from session"""
        if self._use_redis:
            return await self.redis.get_session_images(session_id)  # type: ignore
        elif self.supabase:
            return await self.supabase.get_session_images(session_id)
        return []
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if self._use_redis:
            return await self.redis.delete_session(session_id)  # type: ignore
        elif self.supabase:
            return await self.supabase.delete_session(session_id)
        return False
    
    async def update_metadata(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """Update session metadata (Redis only)"""
        if self._use_redis:
            return await self.redis.update_metadata(session_id, metadata)  # type: ignore
        # Supabase doesn't support metadata updates
        return False
