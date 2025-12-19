"""Redis-based session storage for distributed bot instances"""

import json
import time
from typing import Optional, List, Dict, Any
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None


class RedisSessionStorage:
    """
    Redis-based session storage for multi-PDF collection sessions.
    Replaces Supabase sessions for better performance and scalability.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis session storage.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        self.redis_url = redis_url
        self.redis_client = None
        self._enabled = False
        
    async def connect(self):
        """Establish connection to Redis"""
        if not REDIS_AVAILABLE:
            print("⚠️ Redis library not available. Install with: pip install redis[asyncio]")
            return False
            
        if not self.redis_url:
            print("⚠️ REDIS_URL not configured. Using in-memory fallback.")
            return False
            
        try:
            self.redis_client = await aioredis.from_url(  # type: ignore
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            await self.redis_client.ping()  # type: ignore
            self._enabled = True
            print(f"✅ Redis connected: {self.redis_url}")
            return True
        except Exception as e:
            # Silently fall back to Supabase if Redis unavailable
            self.redis_client = None
            self._enabled = False
            return False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            print("🔌 Redis disconnected")
    
    @property
    def is_enabled(self) -> bool:
        """Check if Redis is enabled and connected"""
        return self._enabled and self.redis_client is not None
    
    # Session Management
    
    async def create_session(self, user_id: int, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Create a new session for a user.
        
        Args:
            user_id: Telegram user ID
            metadata: Optional session metadata (filename, etc.)
            
        Returns:
            Session ID (format: userid_timestamp)
        """
        if not self.is_enabled:
            return None
            
        session_id = f"{user_id}_{int(time.time())}"
        
        session_data = {
            "user_id": user_id,
            "created_at": int(time.time()),
            "images": [],
            "metadata": metadata or {}
        }
        
        try:
            # Store session with 1 hour TTL
            await self.redis_client.setex(  # type: ignore
                f"session:{session_id}",
                3600,  # 1 hour expiration
                json.dumps(session_data)
            )
            
            # Map user_id to session_id for quick lookup
            await self.redis_client.setex(  # type: ignore
                f"user_session:{user_id}",
                3600,
                session_id
            )
            
            return session_id
        except Exception as e:
            print(f"❌ Redis create_session error: {e}")
            return None  # type: ignore
    
    async def get_user_session(self, user_id: int) -> Optional[str]:
        """
        Get active session ID for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Session ID if exists, None otherwise
        """
        if not self.is_enabled:
            return None
            
        try:
            session_id = await self.redis_client.get(f"user_session:{user_id}")  # type: ignore
            return session_id
        except Exception as e:
            print(f"❌ Redis get_user_session error: {e}")
            return None  # type: ignore
    
    async def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data dictionary or None
        """
        if not self.is_enabled:
            return None
            
        try:
            data = await self.redis_client.get(f"session:{session_id}")  # type: ignore
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"❌ Redis get_session_data error: {e}")
            return None
    
    async def add_image(self, session_id: str, image_path: str, order: int) -> bool:
        """
        Add an image to a session.
        
        Args:
            session_id: Session identifier
            image_path: Local file path to image
            order: Image order in the collection
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled:
            return False
            
        try:
            # Get current session data
            session_data = await self.get_session_data(session_id)
            if not session_data:
                return False
            
            # Add image to list
            session_data["images"].append({
                "path": image_path,
                "order": order,
                "added_at": int(time.time())
            })
            
            # Update session
            await self.redis_client.setex(  # type: ignore
                f"session:{session_id}",
                3600,
                json.dumps(session_data)
            )
            
            return True
        except Exception as e:
            print(f"❌ Redis add_image error: {e}")
            return False
    
    async def get_session_images(self, session_id: str) -> List[str]:
        """
        Get all image paths for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of image file paths, ordered by addition
        """
        if not self.is_enabled:
            return []
            
        try:
            session_data = await self.get_session_data(session_id)
            if not session_data:
                return []
            
            # Sort by order and return paths
            images = sorted(session_data["images"], key=lambda x: x["order"])
            return [img["path"] for img in images]
        except Exception as e:
            print(f"❌ Redis get_session_images error: {e}")
            return []
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled:
            return False
            
        try:
            # Get session data to find user_id
            session_data = await self.get_session_data(session_id)
            
            # Delete session data
            await self.redis_client.delete(f"session:{session_id}")  # type: ignore
            
            # Delete user mapping if exists
            if session_data and "user_id" in session_data:
                await self.redis_client.delete(f"user_session:{session_data['user_id']}")  # type: ignore
            
            return True
        except Exception as e:
            print(f"❌ Redis delete_session error: {e}")
            return False
    
    async def update_metadata(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update session metadata.
        
        Args:
            session_id: Session identifier
            metadata: Metadata dictionary to merge
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled:
            return False
            
        try:
            session_data = await self.get_session_data(session_id)
            if not session_data:
                return False
            
            # Merge metadata
            session_data["metadata"].update(metadata)
            
            # Update session
            await self.redis_client.setex(  # type: ignore
                f"session:{session_id}",
                3600,
                json.dumps(session_data)
            )
            
            return True
        except Exception as e:
            print(f"❌ Redis update_metadata error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get Redis statistics.
        
        Returns:
            Dictionary with Redis stats
        """
        if not self.is_enabled:
            return {"enabled": False}
            
        try:
            info = await self.redis_client.info()  # type: ignore
            session_count = len(await self.redis_client.keys("session:*"))  # type: ignore
            
            return {
                "enabled": True,
                "connected": True,
                "active_sessions": session_count,
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            return {
                "enabled": True,
                "connected": False,
                "error": str(e)
            }
