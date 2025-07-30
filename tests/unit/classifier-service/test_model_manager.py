import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
import os

from services.classifier_service.app.ai.model_manager import AIModelManager, ModelProvider


class TestAIModelManager:
    """Test suite for AIModelManager"""

    @pytest.fixture
    def manager(self):
        """Create AI model manager with test configuration"""
        with patch.dict(os.environ, {
            'PRIMARY_AI_MODEL': 'openai',
            'FALLBACK_AI_MODEL': 'google',
            'MODEL_TEMPERATURE': '0.1',
            'MAX_TOKENS': '1000',
            'OPENAI_API_KEY': 'test-openai-key',
            'GOOGLE_API_KEY': 'test-google-key'
        }):
            return AIModelManager()

    def test_initialization(self, manager):
        """Test manager initialization"""
        assert manager.primary_model == ModelProvider.OPENAI
        assert manager.fallback_model == ModelProvider.GOOGLE
        assert manager.temperature == 0.1
        assert manager.max_tokens == 1000

    @pytest.mark.asyncio
    async def test_classify_message_success_primary(self, manager):
        """Test successful classification with primary model"""
        expected_result = {
            "is_support_incident": True,
            "confidence": 0.85,
            "category": "technical",
            "urgency": "high",
            "summary": "Sistema POS no funciona",
            "requires_followup": False,
            "suggested_response": "Hemos recibido tu reporte",
            "extracted_info": {"user_type": "customer"}
        }

        with patch.object(manager, '_call_model') as mock_call:
            mock_call.return_value = expected_result
            
            result = await manager.classify_message("El sistema POS no funciona")
            
            assert result == expected_result
            mock_call.assert_called_once_with(ModelProvider.OPENAI, manager._build_classification_prompt("El sistema POS no funciona", None))

    @pytest.mark.asyncio
    async def test_classify_message_fallback_to_secondary(self, manager):
        """Test fallback to secondary model when primary fails"""
        expected_result = {
            "is_support_incident": True,
            "confidence": 0.75,
            "category": "technical",
            "urgency": "medium",
            "summary": "Problema técnico",
            "requires_followup": True,
            "suggested_response": "Revisaremos tu caso",
            "extracted_info": {}
        }

        with patch.object(manager, '_call_model') as mock_call:
            # Primary model fails, secondary succeeds
            mock_call.side_effect = [Exception("Primary failed"), expected_result]
            
            result = await manager.classify_message("Problema con el sistema")
            
            assert result == expected_result
            assert mock_call.call_count == 2
            mock_call.assert_any_call(ModelProvider.OPENAI, manager._build_classification_prompt("Problema con el sistema", None))
            mock_call.assert_any_call(ModelProvider.GOOGLE, manager._build_classification_prompt("Problema con el sistema", None))

    @pytest.mark.asyncio
    async def test_classify_message_all_models_fail(self, manager):
        """Test default classification when all models fail"""
        with patch.object(manager, '_call_model') as mock_call:
            mock_call.side_effect = Exception("All models failed")
            
            result = await manager.classify_message("Test message")
            
            # Should return default classification
            assert result["is_support_incident"] is True  # Conservative approach
            assert result["confidence"] == 0.1
            assert result["category"] == "general_inquiry"
            assert "revisión manual" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_call_openai_success(self, manager):
        """Test successful OpenAI API call"""
        mock_response = {
            "is_support_incident": True,
            "confidence": 0.9,
            "category": "technical"
        }

        mock_openai_response = MagicMock()
        mock_openai_response.choices[0].message.content = json.dumps(mock_response)

        with patch.object(manager, 'openai_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            
            result = await manager._call_openai("Test prompt")
            
            assert result == mock_response
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_google_success(self, manager):
        """Test successful Google Gemini API call"""
        mock_response = {
            "is_support_incident": False,
            "confidence": 0.3,
            "category": "general_inquiry"
        }

        mock_gemini_response = MagicMock()
        mock_gemini_response.text = json.dumps(mock_response)

        with patch.object(manager, 'google_client') as mock_client:
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor.return_value = mock_gemini_response
                
                result = await manager._call_google("Test prompt")
                
                assert result == mock_response

    @pytest.mark.asyncio
    async def test_call_anthropic_success(self, manager):
        """Test successful Anthropic API call"""
        mock_response = {
            "is_support_incident": True,
            "confidence": 0.8,
            "category": "billing"
        }

        mock_http_response = {
            "content": [{"text": json.dumps(mock_response)}]
        }

        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_http_response)
            
            result = await manager._call_anthropic("Test prompt")
            
            assert result == mock_response

    def test_build_classification_prompt(self, manager):
        """Test prompt building"""
        message = "El sistema no funciona"
        context = {"user": "test", "timestamp": "2024-01-01"}
        
        prompt = manager._build_classification_prompt(message, context)
        
        assert message in prompt
        assert "JSON" in prompt
        assert "is_support_incident" in prompt
        assert "confidence" in prompt
        assert "category" in prompt

    def test_build_classification_prompt_no_context(self, manager):
        """Test prompt building without context"""
        message = "Test message"
        
        prompt = manager._build_classification_prompt(message, None)
        
        assert message in prompt
        assert "Context: {}" in prompt

    def test_default_classification(self, manager):
        """Test default classification structure"""
        result = manager._default_classification()
        
        required_fields = [
            "is_support_incident", "confidence", "category", "urgency",
            "summary", "requires_followup", "suggested_response", "extracted_info"
        ]
        
        for field in required_fields:
            assert field in result
        
        assert result["is_support_incident"] is True  # Conservative
        assert result["confidence"] == 0.1
        assert result["category"] == "general_inquiry"

    @pytest.mark.asyncio
    async def test_call_model_provider_not_available(self, manager):
        """Test calling unavailable model provider"""
        # Set clients to None to simulate unavailable providers
        manager.openai_client = None
        
        result = await manager._call_model(ModelProvider.OPENAI, "test prompt")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_call_model_with_exception(self, manager):
        """Test model call with exception handling"""
        with patch.object(manager, '_call_openai') as mock_call:
            mock_call.side_effect = Exception("API Error")
            
            with pytest.raises(Exception):
                await manager._call_model(ModelProvider.OPENAI, "test prompt")

    def test_model_provider_enum(self):
        """Test ModelProvider enum values"""
        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.GOOGLE.value == "google"
        assert ModelProvider.ANTHROPIC.value == "anthropic"

    @pytest.mark.asyncio
    async def test_classify_message_with_context(self, manager):
        """Test classification with context data"""
        context = {
            "message_id": "test-123",
            "sender": "+573001234567",
            "group_id": "120363123456@g.us",
            "has_media": False
        }

        with patch.object(manager, '_call_model') as mock_call:
            mock_call.return_value = {"is_support_incident": True, "confidence": 0.8, "category": "technical"}
            
            await manager.classify_message("Test message", context)
            
            # Verify context was included in prompt
            prompt = mock_call.call_args[0][1]
            assert "message_id" in prompt
            assert "test-123" in prompt