"""Pytest configuration and shared fixtures"""

import pytest
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Test environment configuration
TEST_ENV = {
    'NODE_ENV': 'test',
    'PYTHON_ENV': 'test',
    'REDIS_HOST': 'localhost',
    'REDIS_PORT': '6379',
    'REDIS_DB': '1',  # Use different DB for tests
    'LOG_LEVEL': 'debug',
    
    # Test API keys (fake)
    'OPENAI_API_KEY': 'test-openai-key',
    'GOOGLE_API_KEY': 'test-google-key',
    'ANTHROPIC_API_KEY': 'test-anthropic-key',
    
    # Test Zoho credentials (fake)
    'ZOHO_CLIENT_ID': 'test-zoho-client-id',
    'ZOHO_CLIENT_SECRET': 'test-zoho-client-secret',
    'ZOHO_ORG_ID': 'test-org-id',
    'ZOHO_AUTHORIZATION_CODE': 'test-auth-code',
    'ZOHO_REDIRECT_URI': 'http://localhost:8003/test/callback'
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables for all tests"""
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    mock_client = MagicMock()
    
    # Mock async methods
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.publish = AsyncMock(return_value=1)
    mock_client.subscribe = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.lpush = AsyncMock(return_value=1)
    mock_client.rpop = AsyncMock(return_value=None)
    mock_client.llen = AsyncMock(return_value=0)
    
    # Mock pub/sub
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = AsyncMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    
    return mock_client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    mock_client = MagicMock()
    
    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"is_support_incident": true, "confidence": 0.8}'
    
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    return mock_client


@pytest.fixture
def mock_zoho_client():
    """Mock Zoho client for testing"""
    mock_client = MagicMock()
    
    # Mock methods
    mock_client.initialize = AsyncMock()
    mock_client.is_connected = MagicMock(return_value=True)
    mock_client.list_departments = AsyncMock(return_value=[
        MagicMock(id='DEPT-001', name='Technical Support', email='tech@test.com')
    ])
    mock_client.create_contact = AsyncMock(return_value='CONTACT-123')
    mock_client.create_ticket = AsyncMock(return_value='TICKET-456')
    mock_client.get_ticket_status = AsyncMock(return_value='Open')
    mock_client.update_ticket = AsyncMock(return_value={'id': 'TICKET-456'})
    
    return mock_client


@pytest.fixture
def mock_whatsapp_service():
    """Mock WhatsApp service for testing"""
    mock_service = MagicMock()
    
    # Mock properties
    mock_service.isConnected = True
    
    # Mock methods
    mock_service.initialize = AsyncMock()
    mock_service.connectWhatsApp = AsyncMock()
    mock_service.sendMessage = AsyncMock()
    mock_service.downloadMedia = AsyncMock(return_value=b'mock_media_data')
    mock_service.disconnect = AsyncMock()
    mock_service.processGroupMessage = AsyncMock()
    
    return mock_service


@pytest.fixture
def sample_message_context():
    """Sample message context for testing"""
    from datetime import datetime
    
    return {
        'message_id': 'test-message-123',
        'sender': '+573001234567@c.us',
        'group_id': '120363123456@g.us',
        'timestamp': datetime.now(),
        'has_media': False,
        'message_type': 'text'
    }


@pytest.fixture
def sample_classification_response():
    """Sample classification response for testing"""
    return {
        'is_support_incident': True,
        'confidence': 0.85,
        'category': 'technical',
        'urgency': 'high',
        'summary': 'Sistema POS no funciona',
        'requires_followup': False,
        'suggested_response': 'Hemos recibido tu reporte técnico',
        'extracted_info': {
            'user_type': 'customer',
            'product_mentioned': 'POS'
        },
        'trigger_words': ['sistema', 'pos', 'no funciona'],
        'processing_time': 0.15
    }


@pytest.fixture
def sample_ticket_request():
    """Sample ticket request for testing"""
    return {
        'subject': 'Sistema POS no funciona',
        'description': 'El sistema POS de la tienda principal no está funcionando',
        'priority': 'urgent',
        'classification': 'technical',
        'contact_id': '123456789',
        'department_id': '987654321'
    }


# Test data cleanup
@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Clean up any test data after each test"""
    yield
    # Add cleanup logic here if needed
    # For example, clear test Redis database
    pass


# Mock external services
@pytest.fixture
def mock_external_apis(monkeypatch):
    """Mock all external API calls"""
    
    # Mock HTTP clients
    import httpx
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {'status': 'ok'}
    mock_response.raise_for_status.return_value = None
    mock_client.__aenter__.return_value.get.return_value = mock_response
    mock_client.__aenter__.return_value.post.return_value = mock_response
    
    monkeypatch.setattr(httpx, 'AsyncClient', MagicMock(return_value=mock_client))
    
    return mock_client


# Performance fixtures
@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# Database fixtures (for future use)
@pytest.fixture
async def test_database():
    """Test database fixture (placeholder for future use)"""
    # This would set up a test database
    # For now, we're using Redis and mocking Zoho
    pass


# Custom markers for test categorization
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "redis: mark test as requiring Redis"
    )
    config.addinivalue_line(
        "markers", "external_api: mark test as requiring external APIs"
    )