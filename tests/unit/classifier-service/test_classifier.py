import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.classifier_service.app.agents.classifier import MessageClassifier, classifier
from services.classifier_service.app.models.schemas import MessageContext, ClassificationResponse


class TestMessageClassifier:
    """Test suite for MessageClassifier"""

    @pytest.fixture
    def classifier_instance(self):
        """Create a fresh classifier instance for each test"""
        return MessageClassifier()

    @pytest.fixture
    def sample_context(self):
        """Sample message context for testing"""
        return MessageContext(
            message_id="test-123",
            sender="+573001234567@c.us",
            group_id="120363123456@g.us",
            timestamp=datetime.now(),
            has_media=False,
            message_type="text"
        )

    @pytest.mark.asyncio
    async def test_classify_with_ai_success(self, classifier_instance, sample_context):
        """Test successful AI classification"""
        mock_ai_result = {
            "is_support_incident": True,
            "confidence": 0.85,
            "category": "technical",
            "urgency": "high",
            "summary": "Sistema POS no funciona",
            "requires_followup": False,
            "suggested_response": "Hemos recibido tu reporte técnico",
            "extracted_info": {"user_type": "customer"}
        }

        with patch('services.classifier_service.app.agents.classifier.model_manager') as mock_manager:
            mock_manager.classify_message.return_value = mock_ai_result
            
            result = await classifier_instance.classify("El sistema POS no funciona", sample_context)
            
            assert isinstance(result, ClassificationResponse)
            assert result.is_support_incident is True
            assert result.confidence == 0.85
            assert result.category == "technical"
            assert result.urgency == "high"
            assert result.summary == "Sistema POS no funciona"

    @pytest.mark.asyncio
    async def test_classify_ai_failure_fallback(self, classifier_instance, sample_context):
        """Test fallback to keyword classification when AI fails"""
        with patch('services.classifier_service.app.agents.classifier.model_manager') as mock_manager:
            mock_manager.classify_message.side_effect = Exception("AI model failed")
            
            result = await classifier_instance.classify("El sistema POS no funciona urgente", sample_context)
            
            assert isinstance(result, ClassificationResponse)
            assert result.is_support_incident is True
            assert result.category == "technical"
            assert result.urgency == "critical"
            assert "urgente" in result.trigger_words

    @pytest.mark.asyncio
    async def test_fallback_classification_urgent_keywords(self, classifier_instance):
        """Test fallback classification with urgent keywords"""
        result = classifier_instance._fallback_classification("El sistema está caído urgente no pueden vender")
        
        assert result.is_support_incident is True
        assert result.category == "technical"
        assert result.urgency == "critical"
        assert "urgente" in result.trigger_words
        assert "sistema" in result.trigger_words
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_fallback_classification_technical_keywords(self, classifier_instance):
        """Test fallback classification with technical keywords"""
        result = classifier_instance._fallback_classification("El software del POS tiene un problema")
        
        assert result.is_support_incident is True
        assert result.category == "technical"
        assert result.urgency == "medium"
        assert "software" in result.trigger_words
        assert "pos" in result.trigger_words

    @pytest.mark.asyncio
    async def test_fallback_classification_billing_keywords(self, classifier_instance):
        """Test fallback classification with billing keywords"""
        result = classifier_instance._fallback_classification("Hay un error en la factura del cliente")
        
        assert result.is_support_incident is True
        assert result.category == "billing"
        assert result.urgency == "medium"
        assert "factura" in result.trigger_words

    @pytest.mark.asyncio
    async def test_fallback_classification_non_incident(self, classifier_instance):
        """Test fallback classification for non-incidents"""
        result = classifier_instance._fallback_classification("Hola, ¿cómo están todos hoy?")
        
        assert result.is_support_incident is False
        assert result.category == "not_support"
        assert result.urgency == "low"
        assert result.confidence < 0.5

    def test_extract_trigger_words(self, classifier_instance):
        """Test trigger word extraction"""
        text = "El sistema POS no funciona urgente en la tienda"
        words = classifier_instance._extract_trigger_words(text)
        
        assert "sistema" in words
        assert "pos" in words
        assert "urgente" in words
        assert "tienda" in words
        assert len(set(words)) == len(words)  # No duplicates

    @pytest.mark.asyncio
    async def test_convert_ai_result_success(self, classifier_instance):
        """Test successful AI result conversion"""
        ai_result = {
            "is_support_incident": True,
            "confidence": 0.9,
            "category": "technical",
            "urgency": "high",
            "summary": "Test summary",
            "requires_followup": True,
            "suggested_response": "Test response",
            "extracted_info": {"test": "data"}
        }
        
        result = classifier_instance._convert_ai_result(ai_result, "test message")
        
        assert isinstance(result, ClassificationResponse)
        assert result.is_support_incident is True
        assert result.confidence == 0.9
        assert result.category == "technical"
        assert result.urgency == "high"

    @pytest.mark.asyncio
    async def test_convert_ai_result_invalid_data(self, classifier_instance):
        """Test AI result conversion with invalid data falls back to keyword classification"""
        invalid_ai_result = {
            "invalid_field": "invalid_value"
        }
        
        result = classifier_instance._convert_ai_result(invalid_ai_result, "sistema no funciona")
        
        # Should fall back to keyword classification
        assert isinstance(result, ClassificationResponse)
        assert result.is_support_incident is True  # Because of "sistema no funciona"

    @pytest.mark.asyncio
    async def test_classify_empty_message(self, classifier_instance):
        """Test classification of empty message"""
        result = await classifier_instance.classify("", None)
        
        assert isinstance(result, ClassificationResponse)
        assert result.is_support_incident is False
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_classify_with_context(self, classifier_instance, sample_context):
        """Test classification with message context"""
        with patch('services.classifier_service.app.agents.classifier.model_manager') as mock_manager:
            mock_manager.classify_message.return_value = {
                "is_support_incident": True,
                "confidence": 0.8,
                "category": "technical",
                "urgency": "medium",
                "summary": "Test",
                "requires_followup": False,
                "suggested_response": "Test response",
                "extracted_info": {}
            }
            
            result = await classifier_instance.classify("Test message", sample_context)
            
            # Verify context was passed to AI model
            mock_manager.classify_message.assert_called_once()
            args = mock_manager.classify_message.call_args
            assert args[0][0] == "Test message"  # Message text
            assert "message_id" in args[0][1]    # Context
            assert args[0][1]["message_id"] == "test-123"


class TestClassifierInstance:
    """Test the global classifier instance"""

    def test_classifier_instance_exists(self):
        """Test that global classifier instance is available"""
        assert classifier is not None
        assert isinstance(classifier, MessageClassifier)

    def test_classifier_fallback_keywords_configured(self):
        """Test that fallback keywords are properly configured"""
        assert "urgent" in classifier.fallback_keywords
        assert "technical" in classifier.fallback_keywords
        assert "billing" in classifier.fallback_keywords
        
        # Check some specific keywords
        assert "urgente" in classifier.fallback_keywords["urgent"]
        assert "pos" in classifier.fallback_keywords["technical"]
        assert "factura" in classifier.fallback_keywords["billing"]