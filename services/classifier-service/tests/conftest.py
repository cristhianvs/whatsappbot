"""
Pytest configuration and shared fixtures
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.schemas import MessageData, QuotedMessage, ContextInfo


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    client = MagicMock()
    client.redis = MagicMock()
    client.setex = AsyncMock()
    client.get = AsyncMock()
    client.keys = AsyncMock()
    client.publish = AsyncMock()
    return client


@pytest.fixture
def sample_message_simple():
    """Simple message without quoted content"""
    return MessageData(
        id="msg_001",
        text="Tienda 907 no deja cobrar marca error",
        from_user="5215512345678@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us",
        has_media=False,
        message_type="text",
        chat_type="group",
        participant="5215512345678@s.whatsapp.net"
    )


@pytest.fixture
def sample_message_with_quoted_bot():
    """Message that quotes a bot response"""
    return MessageData(
        id="msg_002",
        text="Sigue sin funcionar",
        from_user="5215512345678@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us",
        has_media=False,
        message_type="text",
        chat_type="group",
        participant="5215512345678@s.whatsapp.net",
        quoted_message=QuotedMessage(
            id="msg_bot_001",
            text="Ticket #12345 creado para: POS (Prioridad Alta)",
            participant="5215530482752@s.whatsapp.net"  # Bot number
        ),
        context_info=ContextInfo(
            quoted_message_id="msg_bot_001"
        )
    )


@pytest.fixture
def sample_message_with_quoted_user():
    """Message that quotes another user (not bot)"""
    return MessageData(
        id="msg_003",
        text="Si, yo tambien tengo ese problema",
        from_user="5215598765432@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us",
        has_media=False,
        message_type="text",
        chat_type="group",
        participant="5215598765432@s.whatsapp.net",
        quoted_message=QuotedMessage(
            id="msg_001",
            text="Tienda 907 no deja cobrar marca error",
            participant="5215512345678@s.whatsapp.net"  # Another user
        ),
        context_info=ContextInfo(
            quoted_message_id="msg_001"
        )
    )


@pytest.fixture
def bot_phone_number():
    """Bot's WhatsApp phone number"""
    return "5215530482752"
