import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from services.whatsapp_service.src.whatsapp_service import WhatsAppService
from services.classifier_service.app.agents.classifier import MessageClassifier
from services.ticket_service.app.services.zoho_client import ZohoClient


class TestMessageFlow:
    """Integration tests for complete message flow"""

    @pytest.fixture
    async def mock_redis(self):
        """Mock Redis client for integration testing"""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.publish = AsyncMock()
        mock_client.subscribe = AsyncMock()
        
        # Mock pub/sub
        mock_pubsub = MagicMock()
        mock_pubsub.listen = AsyncMock()
        mock_client.pubsub.return_value = mock_pubsub
        
        return mock_client

    @pytest.fixture
    def sample_whatsapp_message(self):
        """Sample WhatsApp message for testing"""
        return {
            'key': {
                'id': 'integration-test-123',
                'participant': '+573001234567@c.us',
                'remoteJid': '120363123456@g.us',
                'fromMe': False
            },
            'message': {
                'conversation': 'El sistema POS no funciona urgente, no podemos vender'
            },
            'messageTimestamp': 1640995200
        }

    @pytest.mark.asyncio
    async def test_complete_message_flow_support_incident(
        self, 
        mock_redis, 
        sample_whatsapp_message
    ):
        """Test complete flow for support incident message"""
        
        # Mock WhatsApp Service
        with patch('redis.createClient') as mock_redis_client:
            mock_redis_client.return_value = mock_redis
            
            whatsapp_service = WhatsAppService()
            await whatsapp_service.initialize()
            
            # Step 1: WhatsApp receives message and publishes to Redis
            await whatsapp_service.processGroupMessage(sample_whatsapp_message)
            
            # Verify message was published to inbound channel
            mock_redis.publish.assert_called_once_with(
                'whatsapp:messages:inbound',
                json.dumps({
                    'id': 'integration-test-123',
                    'from': '+573001234567@c.us',
                    'groupId': '120363123456@g.us',
                    'text': 'El sistema POS no funciona urgente, no podemos vender',
                    'timestamp': 1640995200,
                    'hasMedia': False,
                    'messageType': 'text',
                    'rawMessage': sample_whatsapp_message['message']
                })
            )

    @pytest.mark.asyncio
    async def test_classifier_processes_support_incident(self):
        """Test classifier processing of support incident"""
        
        classifier = MessageClassifier()
        
        # Mock AI model manager to return support incident
        with patch('services.classifier_service.app.agents.classifier.model_manager') as mock_manager:
            mock_manager.classify_message.return_value = {
                'is_support_incident': True,
                'confidence': 0.95,
                'category': 'technical',
                'urgency': 'critical',
                'summary': 'Sistema POS no funciona - impide ventas',
                'requires_followup': False,
                'suggested_response': 'Hemos recibido tu reporte urgente del sistema POS',
                'extracted_info': {
                    'user_type': 'customer',
                    'product_mentioned': 'POS',
                    'impact': 'sales_blocked'
                }
            }
            
            result = await classifier.classify(
                'El sistema POS no funciona urgente, no podemos vender'
            )
            
            assert result.is_support_incident is True
            assert result.confidence == 0.95
            assert result.category == 'technical'
            assert result.urgency == 'critical'
            assert 'POS' in result.summary

    @pytest.mark.asyncio
    async def test_ticket_service_creates_ticket(self):
        """Test ticket service creating ticket from classification"""
        
        # Mock classification result
        classification_data = {
            'message_id': 'integration-test-123',
            'group_id': '120363123456@g.us',
            'classification': {
                'is_support_incident': True,
                'confidence': 0.95,
                'category': 'technical',
                'urgency': 'critical',
                'summary': 'Sistema POS no funciona - impide ventas',
                'requires_followup': False,
                'suggested_response': 'Hemos recibido tu reporte urgente',
                'extracted_info': {
                    'user_type': 'customer',
                    'product_mentioned': 'POS'
                }
            }
        }
        
        # Mock Zoho client
        with patch('services.ticket_service.app.services.zoho_client.ZohoClient') as mock_zoho_class:
            mock_zoho = MagicMock()
            mock_zoho.create_contact = AsyncMock(return_value='CONTACT-123')
            mock_zoho.create_ticket = AsyncMock(return_value='TICKET-456')
            mock_zoho.list_departments = AsyncMock(return_value=[
                MagicMock(id='DEPT-789', name='Technical Support')
            ])
            mock_zoho_class.return_value = mock_zoho
            
            # Mock Redis client
            mock_redis_client = MagicMock()
            mock_redis_client.publish_message = AsyncMock()
            
            # Import and test the handler function
            from services.ticket_service.app.main import handle_classification_result
            
            # Patch the global redis_client
            with patch('services.ticket_service.app.main.redis_client', mock_redis_client):
                await handle_classification_result(classification_data)
                
                # Verify contact creation
                mock_zoho.create_contact.assert_called_once()
                
                # Verify ticket creation
                mock_zoho.create_ticket.assert_called_once()
                
                # Verify ticket created event was published
                mock_redis_client.publish_message.assert_called_once_with(
                    'tickets:created',
                    {
                        'ticket_id': 'TICKET-456',
                        'group_id': '120363123456@g.us',
                        'ticket_number': '#TICKET-456',
                        'summary': mock_redis_client.publish_message.call_args[0][1]['summary'],
                        'priority': 'urgent',
                        'timestamp': mock_redis_client.publish_message.call_args[0][1]['timestamp']
                    }
                )

    @pytest.mark.asyncio
    async def test_response_handler_sends_confirmation(self, mock_redis):
        """Test response handler sending confirmation to WhatsApp"""
        
        from services.whatsapp_service.src.handlers.responseHandler import ResponseHandler
        
        # Mock WhatsApp service
        mock_whatsapp_service = MagicMock()
        mock_whatsapp_service.sendMessage = AsyncMock()
        
        with patch('redis.createClient') as mock_redis_client:
            mock_redis_client.return_value = mock_redis
            
            response_handler = ResponseHandler(mock_whatsapp_service)
            await response_handler.initialize()
            
            # Simulate ticket created event
            ticket_data = {
                'groupId': '120363123456@g.us',
                'ticketId': 'TICKET-456',
                'ticketNumber': '#456',
                'summary': 'Sistema POS no funciona - impide ventas'
            }
            
            await response_handler.handleTicketCreated(ticket_data)
            
            # Verify confirmation message was sent
            mock_whatsapp_service.sendMessage.assert_called_once()
            call_args = mock_whatsapp_service.sendMessage.call_args
            
            assert call_args[0][0] == '120363123456@g.us'  # Group ID
            assert '✅ *Ticket creado exitosamente*' in call_args[0][1]
            assert '#456' in call_args[0][1]
            assert 'Sistema POS no funciona' in call_args[0][1]

    @pytest.mark.asyncio
    async def test_end_to_end_non_incident_flow(self):
        """Test complete flow for non-incident message"""
        
        classifier = MessageClassifier()
        
        # Test casual message
        result = await classifier.classify('Hola, ¿cómo están todos hoy?')
        
        assert result.is_support_incident is False
        assert result.category == 'not_support'
        assert result.urgency == 'low'
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_circuit_breaker_zoho_failure(self):
        """Test circuit breaker when Zoho is unavailable"""
        
        from services.ticket_service.app.services.ticket_queue import TicketQueue
        from services.ticket_service.app.models.schemas import TicketRequest
        
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.redis = MagicMock()
        mock_redis_client.redis.lpush = AsyncMock()
        mock_redis_client.set_cache = AsyncMock()
        
        ticket_queue = TicketQueue(mock_redis_client)
        
        # Create sample ticket request
        ticket_request = TicketRequest(
            subject="Sistema POS no funciona",
            description="Test description",
            priority="urgent",
            classification="technical",
            contact_id="123",
            department_id="456"
        )
        
        # Add ticket to queue (simulating Zoho failure)
        queue_id = await ticket_queue.add_ticket(ticket_request)
        
        assert queue_id.startswith('queue_')
        mock_redis_client.redis.lpush.assert_called_once()
        mock_redis_client.set_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_model_fallback_flow(self):
        """Test AI model fallback when primary model fails"""
        
        classifier = MessageClassifier()
        
        with patch('services.classifier_service.app.agents.classifier.model_manager') as mock_manager:
            # Simulate AI failure to test keyword fallback
            mock_manager.classify_message.side_effect = Exception("AI service unavailable")
            
            result = await classifier.classify('El sistema POS está caído urgente')
            
            # Should fall back to keyword classification
            assert result.is_support_incident is True
            assert result.category == 'technical'
            assert result.urgency == 'critical'
            assert 'urgente' in result.trigger_words
            assert 'sistema' in result.trigger_words

    @pytest.mark.asyncio
    async def test_redis_channel_communication(self, mock_redis):
        """Test Redis pub/sub communication between services"""
        
        # Simulate message flow through Redis channels
        channels_used = []
        messages_published = []
        
        def track_publish(channel, message):
            channels_used.append(channel)
            messages_published.append(json.loads(message) if isinstance(message, str) else message)
            return AsyncMock()
        
        mock_redis.publish.side_effect = track_publish
        
        # Step 1: WhatsApp → Classifier
        whatsapp_message = {
            'id': 'test-123',
            'from': '+573001234567@c.us',
            'groupId': '120363123456@g.us',
            'text': 'Sistema no funciona',
            'timestamp': 1640995200,
            'hasMedia': False,
            'messageType': 'text'
        }
        
        await mock_redis.publish('whatsapp:messages:inbound', json.dumps(whatsapp_message))
        
        # Step 2: Classifier → Ticket Service
        classification_result = {
            'message_id': 'test-123',
            'group_id': '120363123456@g.us',
            'classification': {
                'is_support_incident': True,
                'confidence': 0.8,
                'category': 'technical'
            }
        }
        
        await mock_redis.publish('tickets:classify:result', json.dumps(classification_result))
        
        # Step 3: Ticket Service → WhatsApp (confirmation)
        ticket_created = {
            'ticket_id': 'TICKET-123',
            'group_id': '120363123456@g.us',
            'ticket_number': '#123',
            'summary': 'Sistema no funciona'
        }
        
        await mock_redis.publish('tickets:created', json.dumps(ticket_created))
        
        # Verify all channels were used
        expected_channels = [
            'whatsapp:messages:inbound',
            'tickets:classify:result', 
            'tickets:created'
        ]
        
        assert all(channel in channels_used for channel in expected_channels)
        assert len(messages_published) == 3