import redis.asyncio as redis
import json
import os
import structlog

logger = structlog.get_logger()

class RedisClient:
    def __init__(self):
        self.redis = None
        self.url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    async def connect(self):
        try:
            self.redis = redis.from_url(self.url, decode_responses=True)
            await self.redis.ping()
            logger.info("Connected to Redis", url=self.url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")
    
    async def publish(self, channel: str, message: dict):
        try:
            await self.redis.publish(channel, json.dumps(message))
            logger.debug("Message published", channel=channel)
        except Exception as e:
            logger.error("Failed to publish message", error=str(e), channel=channel)
            raise
    
    async def subscribe(self, channel: str):
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error("Failed to subscribe to channel", error=str(e), channel=channel)
            raise
    
    async def set_cache(self, key: str, value: dict, ttl: int = 3600):
        try:
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error("Failed to set cache", error=str(e), key=key)
            raise
    
    async def get_cache(self, key: str):
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error("Failed to get cache", error=str(e), key=key)
            return None