import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
import json

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'services', 'classifier-service'))

from app.main import app
from app.models.schemas import ClassificationRequest, MessageData


class TestClassifierServiceEndpoints:
    """Test suite for Classifier Service FastAPI endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_classification_request(self):
        """Sample classification request"""
        return {
            "message": {
                "id": "test-123",
                "text": "El sistema POS no funciona",
                "from_user": "+573001234567@c.us",
                "timestamp": "2024-01-01T10:00:00",
                "group_id": "120363123456@g.us",
                "has_media": False,
                "message_type": "text"
            }
        }
    
    def test_health_endpoint_success(self, client):
        """Test health check endpoint"""
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': 'test-key',
            'GOOGLE_API_KEY': 'test-key'
        }):
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "healthy"
            assert data["service"] == "classifier-service"
            assert "timestamp" in data
            assert "models_available" in data
            assert "redis_connected" in data
            assert "openai" in data["models_available"]
            assert "google" in data["models_available"]
    
    def test_health_endpoint_no_models(self, client):
        """Test health check when no models are available"""
        with patch.dict('os.environ', {}, clear=True):
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "healthy"
            assert data["models_available"] == []
    
    @patch('app.main.classifier.classify')
    def test_classify_endpoint_success(self, mock_classify, client, sample_classification_request):
        """Test successful classification endpoint"""
        mock_classification_result = MagicMock()
        mock_classification_result.is_support_incident = True
        mock_classification_result.confidence = 0.85
        mock_classification_result.category = "technical"
        mock_classification_result.urgency = "high"
        mock_classification_result.summary = "Sistema POS no funciona"
        mock_classification_result.requires_followup = False
        mock_classification_result.suggested_response = "Test response"
        mock_classification_result.extracted_info = {"user_type": "customer"}
        mock_classification_result.trigger_words = ["sistema", "pos"]
        mock_classification_result.processing_time = 0.15
        
        mock_classify.return_value = mock_classification_result
        
        response = client.post("/classify", json=sample_classification_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_support_incident"] is True
        assert data["confidence"] == 0.85
        assert data["category"] == "technical"
        assert data["urgency"] == "high"
        assert data["processing_time"] == 0.15
        
        # Verify classifier was called with correct parameters
        mock_classify.assert_called_once()
        call_args = mock_classify.call_args
        assert call_args[1]["text"] == "El sistema POS no funciona"
        assert call_args[1]["context"] is not None
    
    @patch('app.main.classifier.classify')
    def test_classify_endpoint_error(self, mock_classify, client, sample_classification_request):
        """Test classification endpoint with error"""
        mock_classify.side_effect = Exception("Classification failed")
        
        response = client.post("/classify", json=sample_classification_request)
        
        assert response.status_code == 500
        assert "Classification failed" in response.json()["detail"]
    
    def test_classify_endpoint_invalid_request(self, client):
        """Test classification endpoint with invalid request"""
        invalid_request = {
            "message": {
                "id": "test-123"
                # Missing required fields
            }
        }
        
        response = client.post("/classify", json=invalid_request)
        
        assert response.status_code == 422  # Validation error
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "classifier-service"
        assert "timestamp" in data
        assert "metrics_endpoint" in data


class TestMessageHandling:
    """Test suite for WhatsApp message handling"""
    
    @pytest.fixture
    def sample_whatsapp_message(self):
        """Sample WhatsApp message data"""
        return {
            "id": "message-123",
            "from": "+573001234567@c.us",
            "groupId": "120363123456@g.us",
            "text": "El sistema POS no está funcionando",
            "timestamp": 1640995200,  # 2022-01-01 00:00:00
            "hasMedia": False,
            "messageType": "text"
        }
    
    @patch('app.main.classifier.classify')
    @patch('app.main.redis_client.publish_message')
    @pytest.mark.asyncio
    async def test_handle_whatsapp_message_incident(self, mock_publish, mock_classify, sample_whatsapp_message):
        """Test handling WhatsApp message that is classified as incident"""
        from app.main import handle_whatsapp_message
        
        # Mock classification result
        mock_classification_result = MagicMock()
        mock_classification_result.is_support_incident = True
        mock_classification_result.confidence = 0.85
        mock_classification_result.category = "technical"
        mock_classification_result.suggested_response = "Test response"
        mock_classification_result.dict.return_value = {
            "is_support_incident": True,
            "confidence": 0.85,
            "category": "technical"
        }
        
        mock_classify.return_value = mock_classification_result
        mock_publish.return_value = True
        
        await handle_whatsapp_message(sample_whatsapp_message)
        
        # Verify classification was called
        mock_classify.assert_called_once()
        
        # Verify message was published to ticket service
        mock_publish.assert_called()
        publish_calls = mock_publish.call_args_list
        
        # Should publish to tickets:classify:result
        ticket_publish_call = [call for call in publish_calls if call[0][0] == 'tickets:classify:result']
        assert len(ticket_publish_call) > 0
        
        # If high confidence, should also publish suggested response
        if mock_classification_result.confidence > 0.7:
            response_publish_call = [call for call in publish_calls if call[0][0] == 'agents:responses']
            assert len(response_publish_call) > 0
    
    @patch('app.main.classifier.classify')
    @patch('app.main.redis_client.publish_message')
    @pytest.mark.asyncio
    async def test_handle_whatsapp_message_non_incident(self, mock_publish, mock_classify, sample_whatsapp_message):
        """Test handling WhatsApp message that is not an incident"""
        from app.main import handle_whatsapp_message
        
        # Mock classification result - not an incident
        mock_classification_result = MagicMock()
        mock_classification_result.is_support_incident = False
        mock_classification_result.confidence = 0.3
        mock_classification_result.category = "general_inquiry"
        mock_classification_result.dict.return_value = {
            "is_support_incident": False,
            "confidence": 0.3,
            "category": "general_inquiry"
        }
        
        mock_classify.return_value = mock_classification_result
        
        await handle_whatsapp_message(sample_whatsapp_message)
        
        # Verify classification was called
        mock_classify.assert_called_once()
        
        # Should not publish to ticket service for non-incidents
        mock_publish.assert_not_called()
    
    @patch('app.main.classifier.classify')
    @pytest.mark.asyncio
    async def test_handle_whatsapp_message_error(self, mock_classify, sample_whatsapp_message):
        """Test handling WhatsApp message with classification error"""
        from app.main import handle_whatsapp_message
        
        mock_classify.side_effect = Exception("Classification error")
        
        # Should not raise exception but handle gracefully
        await handle_whatsapp_message(sample_whatsapp_message)
        
        mock_classify.assert_called_once()


class TestLifecycleEvents:
    """Test suite for application lifecycle events"""
    
    @patch('app.main.redis_client.connect')
    @patch('app.main.start_message_subscriber')
    @pytest.mark.asyncio
    async def test_startup_event(self, mock_start_subscriber, mock_redis_connect):
        """Test application startup"""
        from app.main import lifespan
        
        mock_redis_connect.return_value = None
        mock_start_subscriber.return_value = MagicMock()
        
        # Test startup
        async with lifespan(app):
            mock_redis_connect.assert_called_once()
            mock_start_subscriber.assert_called_once()
    
    @patch('app.main.redis_client.disconnect')
    @patch('app.main.redis_client.connect')
    @patch('app.main.start_message_subscriber')
    @pytest.mark.asyncio
    async def test_shutdown_event(self, mock_start_subscriber, mock_redis_connect, mock_redis_disconnect):
        """Test application shutdown"""
        from app.main import lifespan
        
        mock_task = MagicMock()
        mock_start_subscriber.return_value = mock_task
        
        # Test full lifecycle
        async with lifespan(app):
            pass
        
        # Verify shutdown cleanup
        mock_task.cancel.assert_called_once()
        mock_redis_disconnect.assert_called_once()