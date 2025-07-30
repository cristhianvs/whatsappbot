import redis.asyncio as redis
import json
import os
import structlog
from typing import Optional, Dict, Any

logger = structlog.get_logger()

class RedisClient:
    def __init__(self):
        self.redis = None
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.password = os.getenv('REDIS_PASSWORD', None)
        
        # Build Redis URL
        if self.password:
            self.url = f"redis://:{self.password}@{self.host}:{self.port}"
        else:
            self.url = f"redis://{self.host}:{self.port}"
    
    async def connect(self):
        try:
            self.redis = redis.from_url(self.url, decode_responses=True)
            await self.redis.ping()
            logger.info("Connected to Redis", host=self.host, port=self.port)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")
    
    async def publish_message(self, channel: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a Redis channel"""
        try:
            message_json = json.dumps(message)
            result = await self.redis.publish(channel, message_json)
            logger.info("Message published", channel=channel, subscribers=result)
            return True
        except Exception as e:
            logger.error("Failed to publish message", channel=channel, error=str(e))
            return False
    
    async def subscribe_to_channel(self, channel: str):
        """Subscribe to a Redis channel"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            logger.info("Subscribed to channel", channel=channel)
            return pubsub
        except Exception as e:
            logger.error("Failed to subscribe to channel", channel=channel, error=str(e))
            return None
    
    async def set_cache(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> bool:
        """Cache a value with TTL"""
        try:
            await self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error("Failed to set cache", error=str(e), key=key)
            return False
    
    async def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached value"""
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error("Failed to get cache", error=str(e), key=key)
            return None

    async def add_to_stream(self, stream_name: str, data: Dict[str, Any]) -> Optional[str]:
        """Add message to Redis Stream"""
        try:
            message_id = await self.redis.xadd(stream_name, data)
            logger.info("Message added to stream", stream=stream_name, message_id=message_id)
            return message_id
        except Exception as e:
            logger.error("Failed to add to stream", stream=stream_name, error=str(e))
            return None