"""
Tests for message schemas
"""
import pytest
from datetime import datetime
from app.models.schemas import MessageData, QuotedMessage, ContextInfo


def test_message_data_simple():
    """Test creating a simple message without quoted content"""
    message = MessageData(
        id="test_001",
        text="Test message",
        from_user="5215512345678@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us"
    )

    assert message.id == "test_001"
    assert message.text == "Test message"
    assert message.quoted_message is None
    assert message.context_info is None


def test_message_data_with_quoted():
    """Test creating a message with quoted content"""
    quoted = QuotedMessage(
        id="original_msg",
        text="Original message text",
        participant="5215598765432@s.whatsapp.net"
    )

    message = MessageData(
        id="test_002",
        text="Reply to original",
        from_user="5215512345678@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us",
        quoted_message=quoted
    )

    assert message.quoted_message is not None
    assert message.quoted_message.id == "original_msg"
    assert message.quoted_message.text == "Original message text"
    assert message.quoted_message.participant == "5215598765432@s.whatsapp.net"


def test_context_info():
    """Test context info structure"""
    context = ContextInfo(
        quoted_message_id="msg_123",
        mentioned_jids=["5215512345678@s.whatsapp.net"],
        is_forwarded=False
    )

    assert context.quoted_message_id == "msg_123"
    assert len(context.mentioned_jids) == 1
    assert context.is_forwarded is False


def test_message_data_full():
    """Test creating a complete message with all fields"""
    quoted = QuotedMessage(
        id="original_msg",
        text="Ticket #12345 creado",
        participant="5215530482752@s.whatsapp.net"
    )

    context = ContextInfo(
        quoted_message_id="original_msg",
        mentioned_jids=[],
        is_forwarded=False
    )

    message = MessageData(
        id="test_003",
        text="Sigue sin funcionar",
        from_user="5215512345678@s.whatsapp.net",
        timestamp=datetime.now(),
        group_id="120363123456789012@g.us",
        has_media=False,
        message_type="text",
        quoted_message=quoted,
        context_info=context,
        chat_type="group",
        participant="5215512345678@s.whatsapp.net"
    )

    assert message.id == "test_003"
    assert message.text == "Sigue sin funcionar"
    assert message.chat_type == "group"
    assert message.quoted_message.text == "Ticket #12345 creado"
    assert message.context_info.quoted_message_id == "original_msg"


def test_message_data_dict_conversion():
    """Test that MessageData can be converted to dict"""
    message = MessageData(
        id="test_004",
        text="Test",
        from_user="5215512345678@s.whatsapp.net",
        timestamp=datetime.now()
    )

    message_dict = message.model_dump()

    assert isinstance(message_dict, dict)
    assert message_dict['id'] == "test_004"
    assert message_dict['text'] == "Test"
