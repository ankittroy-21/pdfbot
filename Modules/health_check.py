"""Health check and monitoring endpoints for the bot"""

import time
import asyncio
from aiohttp import web
from typing import Dict, Any


class HealthCheckServer:
    """HTTP server for health checks and monitoring"""
    
    def __init__(self, bot_app, redis_storage=None, port=8080):
        """
        Initialize health check server.
        
        Args:
            bot_app: Pyrogram Client instance
            redis_storage: RedisSessionStorage instance (optional)
            port: HTTP port to listen on
        """
        self.bot_app = bot_app
        self.redis_storage = redis_storage
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.start_time = time.time()
        
        # Setup routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/metrics', self.metrics)
        self.app.router.add_get('/', self.root)
    
    async def root(self, request):
        """Root endpoint"""
        return web.json_response({
            "service": "PDF Bot",
            "status": "running",
            "endpoints": {
                "/health": "Health check endpoint",
                "/metrics": "Metrics and statistics"
            }
        })
    
    async def health_check(self, request):
        """
        Health check endpoint for Docker/Kubernetes.
        Returns 200 if bot is healthy, 503 otherwise.
        """
        try:
            # Check if bot is connected
            is_connected = self.bot_app.is_connected if hasattr(self.bot_app, 'is_connected') else True
            
            # Check Redis if available
            redis_healthy = True
            if self.redis_storage and self.redis_storage.is_enabled:
                try:
                    await self.redis_storage.redis_client.ping()
                except:
                    redis_healthy = False
            
            # Overall health
            healthy = is_connected and redis_healthy
            
            response = {
                "status": "healthy" if healthy else "unhealthy",
                "timestamp": int(time.time()),
                "uptime_seconds": int(time.time() - self.start_time),
                "checks": {
                    "bot_connected": is_connected,
                    "redis_connected": redis_healthy if self.redis_storage else "not_configured"
                }
            }
            
            status_code = 200 if healthy else 503
            return web.json_response(response, status=status_code)
            
        except Exception as e:
            return web.json_response({
                "status": "unhealthy",
                "error": str(e),
                "timestamp": int(time.time())
            }, status=503)
    
    async def metrics(self, request):
        """
        Metrics endpoint for monitoring.
        Returns statistics about bot operation.
        """
        try:
            metrics_data: Dict[str, Any] = {
                "uptime_seconds": int(time.time() - self.start_time),
                "timestamp": int(time.time())
            }
            
            # Add Redis stats if available
            if self.redis_storage and self.redis_storage.is_enabled:
                try:
                    redis_stats = await self.redis_storage.get_stats()
                    metrics_data["redis"] = redis_stats
                except Exception as e:
                    metrics_data["redis"] = {"error": str(e)}
            else:
                metrics_data["redis"] = {"enabled": False}
            
            return web.json_response(metrics_data)
            
        except Exception as e:
            return web.json_response({
                "error": str(e),
                "timestamp": int(time.time())
            }, status=500)
    
    async def start(self):
        """Start the health check server"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await site.start()
            print(f"✅ Health check server started on port {self.port}")
            print(f"   - Health: http://0.0.0.0:{self.port}/health")
            print(f"   - Metrics: http://0.0.0.0:{self.port}/metrics")
        except Exception as e:
            print(f"❌ Failed to start health check server: {e}")
    
    async def stop(self):
        """Stop the health check server"""
        if self.runner:
            await self.runner.cleanup()
            print("🛑 Health check server stopped")
