import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from services.ticket_service.app.services.ticket_queue import TicketQueue
from services.ticket_service.app.models.schemas import TicketRequest


class TestTicketQueue:
    """Test suite for TicketQueue"""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for testing"""
        mock_client = MagicMock()
        mock_client.redis = MagicMock()
        mock_client.redis.lpush = AsyncMock()
        mock_client.redis.rpop = AsyncMock()
        mock_client.redis.llen = AsyncMock()
        mock_client.set_cache = AsyncMock()
        mock_client.get_cache = AsyncMock()
        mock_client.publish_message = AsyncMock()
        return mock_client

    @pytest.fixture
    def ticket_queue(self, mock_redis_client):
        """Create TicketQueue with mock Redis client"""
        return TicketQueue(mock_redis_client)

    @pytest.fixture
    def sample_ticket_request(self):
        """Sample ticket request for testing"""
        return TicketRequest(
            subject="Sistema POS no funciona",
            description="El sistema está caído en la tienda principal",
            priority="urgent",
            classification="technical",
            contact_id="123456789",
            department_id="987654321"
        )

    @pytest.mark.asyncio
    async def test_add_ticket_success(self, ticket_queue, mock_redis_client, sample_ticket_request):
        """Test successful ticket addition to queue"""
        queue_id = await ticket_queue.add_ticket(sample_ticket_request)
        
        assert queue_id.startswith("queue_")
        assert len(queue_id) == 14  # "queue_" + 8 hex chars
        
        # Verify Redis operations
        mock_redis_client.redis.lpush.assert_called_once()
        mock_redis_client.set_cache.assert_called_once()
        
        # Verify queue item structure
        lpush_call = mock_redis_client.redis.lpush.call_args
        queue_item_json = lpush_call[0][1]
        queue_item = json.loads(queue_item_json)
        
        assert queue_item['id'] == queue_id
        assert queue_item['attempts'] == 0
        assert queue_item['max_attempts'] == 10
        assert queue_item['status'] == 'queued'
        assert queue_item['ticket_data']['subject'] == sample_ticket_request.subject

    @pytest.mark.asyncio
    async def test_add_ticket_redis_failure(self, ticket_queue, mock_redis_client, sample_ticket_request):
        """Test ticket addition with Redis failure"""
        mock_redis_client.redis.lpush.side_effect = Exception("Redis error")
        
        with pytest.raises(Exception, match="Redis error"):
            await ticket_queue.add_ticket(sample_ticket_request)

    @pytest.mark.asyncio
    async def test_get_ticket_status_found(self, ticket_queue, mock_redis_client):
        """Test getting status of existing queued ticket"""
        mock_status = {
            'status': 'queued',
            'created_at': '2024-01-01T10:00:00',
            'last_updated': '2024-01-01T10:00:00'
        }
        mock_redis_client.get_cache.return_value = mock_status
        
        result = await ticket_queue.get_ticket_status('queue_12345678')
        
        assert result == mock_status
        mock_redis_client.get_cache.assert_called_once_with('ticket_status:queue_12345678')

    @pytest.mark.asyncio
    async def test_get_ticket_status_not_found(self, ticket_queue, mock_redis_client):
        """Test getting status of non-existent ticket"""
        mock_redis_client.get_cache.return_value = None
        
        result = await ticket_queue.get_ticket_status('queue_nonexistent')
        
        assert result['status'] == 'not_found'
        assert 'last_updated' in result

    @pytest.mark.asyncio
    async def test_get_ticket_status_redis_error(self, ticket_queue, mock_redis_client):
        """Test getting status with Redis error"""
        mock_redis_client.get_cache.side_effect = Exception("Redis error")
        
        result = await ticket_queue.get_ticket_status('queue_12345678')
        
        assert result['status'] == 'error'
        assert 'last_updated' in result

    @pytest.mark.asyncio
    async def test_process_queue_empty(self, ticket_queue, mock_redis_client):
        """Test processing empty queue"""
        mock_redis_client.redis.rpop.return_value = None
        
        result = await ticket_queue.process_queue()
        
        assert result == 0
        mock_redis_client.redis.rpop.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_queue_success(self, ticket_queue, mock_redis_client, sample_ticket_request):
        """Test successful queue processing"""
        # Mock queue item
        queue_item = {
            'id': 'queue_12345678',
            'ticket_data': sample_ticket_request.dict(),
            'attempts': 0,
            'max_attempts': 10,
            'created_at': '2024-01-01T10:00:00',
            'status': 'queued'
        }
        
        mock_redis_client.redis.rpop.side_effect = [
            json.dumps(queue_item),
            None  # Empty queue after first item
        ]
        
        # Mock Zoho client
        with patch('services.ticket_service.app.services.ticket_queue.ZohoClient') as mock_zoho_class:
            mock_zoho = MagicMock()
            mock_zoho.initialize = AsyncMock()
            mock_zoho.create_ticket = AsyncMock(return_value='TICKET-123')
            mock_zoho_class.return_value = mock_zoho
            
            result = await ticket_queue.process_queue()
            
            assert result == 1
            mock_zoho.create_ticket.assert_called_once()
            mock_redis_client.set_cache.assert_called()
            mock_redis_client.publish_message.assert_called_once_with(
                'tickets:created',
                {
                    'ticket_id': 'TICKET-123',
                    'queue_id': 'queue_12345678',
                    'subject': sample_ticket_request.subject,
                    'priority': sample_ticket_request.priority,
                    'contact_id': sample_ticket_request.contact_id,
                    'timestamp': mock_redis_client.publish_message.call_args[0][1]['timestamp']
                }
            )

    @pytest.mark.asyncio
    async def test_process_queue_retry_on_failure(self, ticket_queue, mock_redis_client, sample_ticket_request):
        """Test queue processing with retry on failure"""
        queue_item = {
            'id': 'queue_12345678',
            'ticket_data': sample_ticket_request.dict(),
            'attempts': 0,
            'max_attempts': 10,
            'created_at': '2024-01-01T10:00:00',
            'status': 'queued'
        }
        
        mock_redis_client.redis.rpop.side_effect = [
            json.dumps(queue_item),
            None
        ]
        
        # Mock Zoho client failure
        with patch('services.ticket_service.app.services.ticket_queue.ZohoClient') as mock_zoho_class:
            mock_zoho = MagicMock()
            mock_zoho.initialize = AsyncMock()
            mock_zoho.create_ticket = AsyncMock(side_effect=Exception("Zoho API error"))
            mock_zoho_class.return_value = mock_zoho
            
            result = await ticket_queue.process_queue()
            
            assert result == 0  # No successful processing
            
            # Verify item was re-queued with incremented attempts
            lpush_calls = mock_redis_client.redis.lpush.call_args_list
            assert len(lpush_calls) == 1
            
            requeued_item = json.loads(lpush_calls[0][0][1])
            assert requeued_item['attempts'] == 1
            assert requeued_item['error'] == 'Zoho API error'

    @pytest.mark.asyncio
    async def test_process_queue_max_attempts_reached(self, ticket_queue, mock_redis_client, sample_ticket_request):
        """Test queue processing when max attempts reached"""
        queue_item = {
            'id': 'queue_12345678',
            'ticket_data': sample_ticket_request.dict(),
            'attempts': 9,  # One less than max
            'max_attempts': 10,
            'created_at': '2024-01-01T10:00:00',
            'status': 'retrying'
        }
        
        mock_redis_client.redis.rpop.side_effect = [
            json.dumps(queue_item),
            None
        ]
        
        # Mock Zoho client failure
        with patch('services.ticket_service.app.services.ticket_queue.ZohoClient') as mock_zoho_class:
            mock_zoho = MagicMock()
            mock_zoho.initialize = AsyncMock()
            mock_zoho.create_ticket = AsyncMock(side_effect=Exception("Zoho API error"))
            mock_zoho_class.return_value = mock_zoho
            
            result = await ticket_queue.process_queue()
            
            assert result == 0
            
            # Verify item was not re-queued (max attempts reached)
            mock_redis_client.redis.lpush.assert_not_called()
            
            # Verify status was set to failed
            set_cache_calls = mock_redis_client.set_cache.call_args_list
            failed_status = set_cache_calls[0][0][1]
            assert failed_status['status'] == 'failed'
            assert failed_status['attempts'] == 10

    @pytest.mark.asyncio
    async def test_get_queue_length_success(self, ticket_queue, mock_redis_client):
        """Test successful queue length retrieval"""
        mock_redis_client.redis.llen.return_value = 5
        
        length = await ticket_queue.get_queue_length()
        
        assert length == 5
        mock_redis_client.redis.llen.assert_called_once_with('pending_tickets')

    @pytest.mark.asyncio
    async def test_get_queue_length_error(self, ticket_queue, mock_redis_client):
        """Test queue length retrieval with error"""
        mock_redis_client.redis.llen.side_effect = Exception("Redis error")
        
        length = await ticket_queue.get_queue_length()
        
        assert length == 0

    @pytest.mark.asyncio
    async def test_get_queue_stats_success(self, ticket_queue, mock_redis_client):
        """Test successful queue stats retrieval"""
        mock_redis_client.redis.llen.return_value = 3
        
        stats = await ticket_queue.get_queue_stats()
        
        assert stats['queue_length'] == 3
        assert 'last_check' in stats

    @pytest.mark.asyncio
    async def test_get_queue_stats_error(self, ticket_queue, mock_redis_client):
        """Test queue stats retrieval with error"""
        mock_redis_client.redis.llen.side_effect = Exception("Redis error")
        
        stats = await ticket_queue.get_queue_stats()
        
        assert stats['queue_length'] == -1
        assert 'error' in stats
        assert 'last_check' in stats

    @pytest.mark.asyncio
    async def test_process_queue_json_parse_error(self, ticket_queue, mock_redis_client):
        """Test queue processing with invalid JSON"""
        mock_redis_client.redis.rpop.side_effect = [
            "invalid json",
            None
        ]
        
        # Should not raise exception, just continue processing
        result = await ticket_queue.process_queue()
        
        assert result == 0