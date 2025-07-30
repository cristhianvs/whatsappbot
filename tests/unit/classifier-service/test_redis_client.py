import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
import json

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'services', 'classifier-service'))

from app.utils.redis_client import RedisClient


class TestRedisClient:
    """Test suite for RedisClient"""
    
    @pytest.fixture
    def redis_client(self):
        """Create Redis client instance"""
        return RedisClient()
    
    def test_redis_client_initialization(self, redis_client):
        """Test Redis client initialization"""
        assert redis_client.host == "localhost"  # Default from test env
        assert redis_client.port == 6379
        assert redis_client.password is None
        assert "redis://localhost:6379" in redis_client.url
    
    def test_redis_client_initialization_with_password(self):
        """Test Redis client initialization with password"""
        with patch.dict(os.environ, {'REDIS_PASSWORD': 'test-password'}):
            client = RedisClient()
            assert client.password == 'test-password'
            assert "redis://:test-password@localhost:6379" == client.url
    
    @patch('redis.asyncio.from_url')
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_from_url, redis_client):
        """Test successful Redis connection"""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_from_url.return_value = mock_redis
        
        await redis_client.connect()
        
        assert redis_client.redis == mock_redis
        mock_from_url.assert_called_once_with(redis_client.url, decode_responses=True)
        mock_redis.ping.assert_called_once()
    
    @patch('redis.asyncio.from_url')
    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_from_url, redis_client):
        """Test Redis connection failure"""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        mock_from_url.return_value = mock_redis
        
        with pytest.raises(Exception, match="Connection failed"):
            await redis_client.connect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, redis_client):
        """Test Redis disconnection"""
        mock_redis = AsyncMock()
        redis_client.redis = mock_redis
        
        await redis_client.disconnect()
        
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_no_connection(self, redis_client):
        """Test disconnect when no connection exists"""
        redis_client.redis = None
        
        # Should not raise exception
        await redis_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_publish_message_success(self, redis_client):
        """Test successful message publishing"""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 2  # 2 subscribers
        redis_client.redis = mock_redis
        
        message = {"test": "data", "number": 123}
        result = await redis_client.publish_message("test-channel", message)
        
        assert result is True
        mock_redis.publish.assert_called_once_with("test-channel", json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_publish_message_failure(self, redis_client):
        """Test message publishing failure"""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Publish failed")
        redis_client.redis = mock_redis
        
        message = {"test": "data"}
        result = await redis_client.publish_message("test-channel", message)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_subscribe_to_channel_success(self, redis_client):
        """Test successful channel subscription"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        redis_client.redis = mock_redis
        
        result = await redis_client.subscribe_to_channel("test-channel")
        
        assert result == mock_pubsub
        mock_redis.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_called_once_with("test-channel")
    
    @pytest.mark.asyncio
    async def test_subscribe_to_channel_failure(self, redis_client):
        """Test channel subscription failure"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock(side_effect=Exception("Subscribe failed"))
        mock_redis.pubsub.return_value = mock_pubsub
        redis_client.redis = mock_redis
        
        result = await redis_client.subscribe_to_channel("test-channel")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_cache_success(self, redis_client):
        """Test successful cache setting"""
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        redis_client.redis = mock_redis
        
        data = {"cached": "data", "count": 42}
        result = await redis_client.set_cache("test-key", data, 1800)
        
        assert result is True
        mock_redis.setex.assert_called_once_with("test-key", 1800, json.dumps(data))
    
    @pytest.mark.asyncio
    async def test_set_cache_default_ttl(self, redis_client):
        """Test cache setting with default TTL"""
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        redis_client.redis = mock_redis
        
        data = {"test": "data"}
        result = await redis_client.set_cache("test-key", data)
        
        assert result is True
        mock_redis.setex.assert_called_once_with("test-key", 3600, json.dumps(data))
    
    @pytest.mark.asyncio
    async def test_set_cache_failure(self, redis_client):
        """Test cache setting failure"""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Cache set failed")
        redis_client.redis = mock_redis
        
        data = {"test": "data"}
        result = await redis_client.set_cache("test-key", data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_cache_success(self, redis_client):
        """Test successful cache retrieval"""
        mock_redis = AsyncMock()
        cached_data = {"retrieved": "data", "value": 100}
        mock_redis.get.return_value = json.dumps(cached_data)
        redis_client.redis = mock_redis
        
        result = await redis_client.get_cache("test-key")
        
        assert result == cached_data
        mock_redis.get.assert_called_once_with("test-key")
    
    @pytest.mark.asyncio
    async def test_get_cache_not_found(self, redis_client):
        """Test cache retrieval when key not found"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        redis_client.redis = mock_redis
        
        result = await redis_client.get_cache("non-existent-key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_cache_failure(self, redis_client):
        """Test cache retrieval failure"""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Cache get failed")
        redis_client.redis = mock_redis
        
        result = await redis_client.get_cache("test-key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_add_to_stream_success(self, redis_client):
        """Test successful stream addition"""
        mock_redis = AsyncMock()
        mock_redis.xadd.return_value = "1640995200000-0"
        redis_client.redis = mock_redis
        
        stream_data = {"field1": "value1", "field2": "value2"}
        result = await redis_client.add_to_stream("test-stream", stream_data)
        
        assert result == "1640995200000-0"
        mock_redis.xadd.assert_called_once_with("test-stream", stream_data)
    
    @pytest.mark.asyncio
    async def test_add_to_stream_failure(self, redis_client):
        """Test stream addition failure"""
        mock_redis = AsyncMock()
        mock_redis.xadd.side_effect = Exception("Stream add failed")
        redis_client.redis = mock_redis
        
        stream_data = {"field": "value"}
        result = await redis_client.add_to_stream("test-stream", stream_data)
        
        assert result is None


class TestRedisClientIntegration:
    """Integration-style tests for Redis client (using mock Redis)"""
    
    @pytest.fixture
    async def connected_redis_client(self):
        """Redis client with mocked connection"""
        client = RedisClient()
        
        # Mock the Redis connection
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            await client.connect()
            
        return client
    
    @pytest.mark.asyncio
    async def test_publish_subscribe_flow(self, connected_redis_client):
        """Test publish-subscribe message flow"""
        # Mock pubsub behavior
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        # Make redis object support both sync and async methods
        connected_redis_client.redis.pubsub = MagicMock(return_value=mock_pubsub)
        connected_redis_client.redis.publish.return_value = 1
        
        # Subscribe to channel
        pubsub = await connected_redis_client.subscribe_to_channel("test-flow")
        assert pubsub == mock_pubsub
        
        # Publish message
        message = {"flow": "test", "data": [1, 2, 3]}
        result = await connected_redis_client.publish_message("test-flow", message)
        assert result is True
        
        # Verify calls
        mock_pubsub.subscribe.assert_called_once_with("test-flow")
        connected_redis_client.redis.publish.assert_called_once_with("test-flow", json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_cache_lifecycle(self, connected_redis_client):
        """Test complete cache lifecycle"""
        # Mock cache operations
        test_data = {"lifecycle": "test", "items": ["a", "b", "c"]}
        json_data = json.dumps(test_data)
        
        connected_redis_client.redis.setex.return_value = True
        connected_redis_client.redis.get.return_value = json_data
        
        # Set cache
        set_result = await connected_redis_client.set_cache("lifecycle-key", test_data, 7200)
        assert set_result is True
        
        # Get cache
        get_result = await connected_redis_client.get_cache("lifecycle-key")
        assert get_result == test_data
        
        # Verify calls
        connected_redis_client.redis.setex.assert_called_once_with("lifecycle-key", 7200, json_data)
        connected_redis_client.redis.get.assert_called_once_with("lifecycle-key")
    
    @pytest.mark.asyncio
    async def test_stream_operations(self, connected_redis_client):
        """Test Redis stream operations"""
        # Mock stream operations
        stream_id = "1640995200000-0"
        connected_redis_client.redis.xadd.return_value = stream_id
        
        # Add to stream
        stream_data = {
            "message_id": "test-123",
            "classification": "technical",
            "confidence": "0.85"
        }
        
        result = await connected_redis_client.add_to_stream("classification-stream", stream_data)
        assert result == stream_id
        
        connected_redis_client.redis.xadd.assert_called_once_with("classification-stream", stream_data)