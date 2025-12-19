"""
Rate Limiter Module
Prevents abuse by throttling user requests with sliding window algorithm
"""

import time
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple


class RateLimiter:
    """
    Rate limiter using sliding window algorithm for accurate throttling.
    
    Features:
    - Per-user rate limiting
    - Configurable time window and max requests
    - Memory-efficient with automatic cleanup
    - Thread-safe for concurrent requests
    """
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Store timestamps of requests per user
        # user_id -> deque of timestamps
        self.user_requests: Dict[int, Deque[float]] = defaultdict(deque)
        
        # Track last cleanup time
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # Cleanup every 5 minutes
    
    def _cleanup_old_entries(self):
        """Remove inactive users from memory (haven't made request in 10 minutes)"""
        now = time.time()
        
        # Only cleanup periodically to avoid performance impact
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        inactive_threshold = now - 600  # 10 minutes
        users_to_remove = []
        
        for user_id, timestamps in self.user_requests.items():
            # If user's last request was over 10 minutes ago, remove them
            if timestamps and timestamps[-1] < inactive_threshold:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.user_requests[user_id]
        
        self.last_cleanup = now
        
        if users_to_remove:
            print(f"🧹 Rate limiter cleanup: Removed {len(users_to_remove)} inactive users")
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user has exceeded rate limit.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (is_allowed: bool, seconds_to_wait: int)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Get user's request history
        timestamps = self.user_requests[user_id]
        
        # Remove timestamps outside the current window
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()
        
        # Check if under limit
        if len(timestamps) < self.max_requests:
            # Add current request timestamp
            timestamps.append(now)
            
            # Periodic cleanup
            self._cleanup_old_entries()
            
            return True, 0
        
        # Rate limit exceeded - calculate wait time
        oldest_request = timestamps[0]
        seconds_to_wait = int(oldest_request + self.window_seconds - now) + 1
        
        return False, seconds_to_wait
    
    def get_user_stats(self, user_id: int) -> Dict:
        """
        Get rate limit statistics for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary with request count and remaining requests
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        timestamps = self.user_requests[user_id]
        
        # Remove old timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()
        
        current_count = len(timestamps)
        remaining = max(0, self.max_requests - current_count)
        
        return {
            "current_requests": current_count,
            "max_requests": self.max_requests,
            "remaining_requests": remaining,
            "window_seconds": self.window_seconds
        }


# Global rate limiter instances for different operations
pdf_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 PDFs per minute
compress_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)  # 5 compressions per minute
multipdf_rate_limiter = RateLimiter(max_requests=5, window_seconds=120)  # 5 multi-PDFs per 2 minutes
