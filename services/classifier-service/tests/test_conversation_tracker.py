"""
Tests for Conversation Tracker
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.conversation_tracker import ConversationTracker
from app.models.schemas import MessageData, QuotedMessage, ContextInfo


async def async_gen(items):
    """Helper to create async generator"""
    for item in items:
        yield item


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = MagicMock()
    redis_mock.redis = AsyncMock()
    redis_mock.get_cache = AsyncMock()
    redis_mock.set_cache = AsyncMock(return_value=True)

    # scan_iter will be set per test
    redis_mock.redis.scan_iter = MagicMock(return_value=async_gen([]))
    redis_mock.redis.keys = AsyncMock(return_value=[])
    return redis_mock


@pytest.fixture
def tracker(mock_redis):
    """Conversation tracker instance"""
    return ConversationTracker(mock_redis, bot_phone_number="5215530482752")


@pytest.mark.asyncio
async def test_extract_ticket_from_quoted_bot_message(tracker, mock_redis, sample_message_with_quoted_bot):
    """Test extracting ticket ID from bot's quoted message"""
    # Mock that ticket is active
    mock_redis.redis.scan_iter = MagicMock(
        return_value=async_gen(["incident:active:120363123456789012@g.us:12345"])
    )
    mock_redis.get_cache = AsyncMock(return_value={
        'ticket_id': '12345',
        'timestamp': datetime.now().isoformat()
    })

    ticket_id = await tracker.check_existing_incident(sample_message_with_quoted_bot)

    assert ticket_id == "12345"


@pytest.mark.asyncio
async def test_no_ticket_from_quoted_user_message(tracker, sample_message_with_quoted_user):
    """Test that messages quoting other users (not bot) don't extract ticket"""
    ticket_id = await tracker.check_existing_incident(sample_message_with_quoted_user)

    assert ticket_id is None


@pytest.mark.asyncio
async def test_register_new_incident(tracker, mock_redis, sample_message_simple):
    """Test registering a new incident"""
    classification = {
        'categoria': 'POS',
        'prioridad': 'alta'
    }

    success = await tracker.register_incident(
        sample_message_simple,
        ticket_id="12345",
        classification=classification
    )

    assert success is True
    mock_redis.set_cache.assert_called_once()

    # Verify the key format
    call_args = mock_redis.set_cache.call_args
    key = call_args[0][0]
    assert key.startswith("incident:active:")
    assert "12345" in key


@pytest.mark.asyncio
async def test_add_message_to_thread(tracker, mock_redis):
    """Test adding message to existing thread"""
    # Mock existing incident
    existing_incident = {
        'ticket_id': '12345',
        'thread_messages': ['msg_001'],
        'timestamp': datetime.now().isoformat()
    }

    mock_redis.redis.scan_iter = AsyncMock(
        return_value=iter(["incident:active:120363123456789012@g.us:12345"])
    )
    mock_redis.get_cache = AsyncMock(return_value=existing_incident)

    success = await tracker.add_message_to_thread(
        ticket_id="12345",
        message_id="msg_002",
        message_text="Sigue sin funcionar"
    )

    assert success is True
    mock_redis.set_cache.assert_called_once()

    # Verify updated incident data
    call_args = mock_redis.set_cache.call_args
    updated_incident = call_args[0][1]
    assert len(updated_incident['thread_messages']) == 2
    assert 'msg_002' in updated_incident['thread_messages']


@pytest.mark.asyncio
async def test_find_recent_incident_within_window(tracker, mock_redis):
    """Test finding recent incident within time window"""
    # Create recent incident (30 minutes ago)
    recent_time = datetime.now() - timedelta(minutes=30)
    recent_incident = {
        'ticket_id': '12345',
        'timestamp': recent_time.isoformat(),
        'group_id': '120363123456789012@g.us'
    }

    # Mock Redis response
    mock_redis.redis.scan_iter = AsyncMock(
        return_value=iter(["incident:active:120363123456789012@g.us:12345"])
    )
    mock_redis.get_cache = AsyncMock(return_value=recent_incident)

    # Create message in same group
    message = MessageData(
        id="msg_new",
        text="Alguien sabe del problema?",
        from_user="5215598765432@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us"
    )

    ticket_id = await tracker.check_existing_incident(message)

    assert ticket_id == "12345"


@pytest.mark.asyncio
async def test_no_incident_outside_time_window(tracker, mock_redis):
    """Test that old incidents are not returned"""
    # Create old incident (3 hours ago, outside 2-hour window)
    old_time = datetime.now() - timedelta(hours=3)
    old_incident = {
        'ticket_id': '12345',
        'timestamp': old_time.isoformat(),
        'group_id': '120363123456789012@g.us'
    }

    # Mock Redis response
    mock_redis.redis.scan_iter = AsyncMock(
        return_value=iter(["incident:active:120363123456789012@g.us:12345"])
    )
    mock_redis.get_cache = AsyncMock(return_value=old_incident)

    # Create message in same group
    message = MessageData(
        id="msg_new",
        text="Nuevo problema",
        from_user="5215598765432@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us"
    )

    ticket_id = await tracker.check_existing_incident(message)

    assert ticket_id is None


@pytest.mark.asyncio
async def test_is_ticket_active(tracker, mock_redis):
    """Test checking if ticket is active"""
    # Mock active ticket
    mock_redis.redis.scan_iter = AsyncMock(
        return_value=iter(["incident:active:120363123456789012@g.us:12345"])
    )

    is_active = await tracker.is_ticket_active("12345")
    assert is_active is True

    # Mock inactive ticket
    mock_redis.redis.scan_iter = AsyncMock(return_value=iter([]))

    is_active = await tracker.is_ticket_active("99999")
    assert is_active is False


@pytest.mark.asyncio
async def test_get_thread_summary(tracker, mock_redis):
    """Test getting thread summary"""
    thread_data = {
        'ticket_id': '12345',
        'thread_messages': ['msg_001', 'msg_002', 'msg_003'],
        'timestamp': datetime.now().isoformat(),
        'category': 'POS',
        'priority': 'alta'
    }

    mock_redis.redis.scan_iter = AsyncMock(
        return_value=iter(["incident:active:120363123456789012@g.us:12345"])
    )
    mock_redis.get_cache = AsyncMock(return_value=thread_data)

    summary = await tracker.get_thread_summary("12345")

    assert summary is not None
    assert summary['ticket_id'] == '12345'
    assert len(summary['thread_messages']) == 3


@pytest.mark.asyncio
async def test_extract_ticket_patterns(tracker, mock_redis):
    """Test different ticket ID patterns in quoted messages"""
    patterns = [
        ("Ticket #12345 creado", "12345"),
        ("Ticket 67890 creado", "67890"),
        ("ticket #11111 creado", "11111"),
        ("Ver #99999 para detalles", "99999"),
    ]

    for quoted_text, expected_ticket_id in patterns:
        # Mock active ticket
        mock_redis.redis.scan_iter = AsyncMock(
            return_value=iter([f"incident:active:group:{expected_ticket_id}"])
        )
        mock_redis.get_cache = AsyncMock(return_value={
            'ticket_id': expected_ticket_id,
            'timestamp': datetime.now().isoformat()
        })

        message = MessageData(
            id="msg_test",
            text="Sigue el problema",
            from_user="5215512345678@s.whatsapp.net",
            timestamp=datetime.now(),
            quoted_message=QuotedMessage(
                id="msg_bot",
                text=quoted_text,
                participant="5215530482752@s.whatsapp.net"  # Bot
            )
        )

        ticket_id = await tracker.check_existing_incident(message)
        assert ticket_id == expected_ticket_id, f"Failed to extract from: {quoted_text}"


@pytest.mark.asyncio
async def test_message_dict_format(tracker, mock_redis):
    """Test that tracker works with dict format (not just MessageData objects)"""
    message_dict = {
        'id': 'msg_001',
        'text': 'Test message',
        'from_user': '5215512345678@s.whatsapp.net',
        'group_id': '120363123456789012@g.us',
        'timestamp': datetime.now().isoformat(),
        'quoted_message': {
            'id': 'msg_bot',
            'text': 'Ticket #12345 creado',
            'participant': '5215530482752@s.whatsapp.net'
        }
    }

    # Mock active ticket
    mock_redis.redis.scan_iter = AsyncMock(
        return_value=iter(["incident:active:120363123456789012@g.us:12345"])
    )
    mock_redis.get_cache = AsyncMock(return_value={
        'ticket_id': '12345',
        'timestamp': datetime.now().isoformat()
    })

    ticket_id = await tracker.check_existing_incident(message_dict)
    assert ticket_id == "12345"
