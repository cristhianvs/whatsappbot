from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class QuotedMessage(BaseModel):
    """Mensaje citado/respondido en WhatsApp"""
    id: str
    text: str
    participant: str  # Quien envió el mensaje original

class ContextInfo(BaseModel):
    """Información de contexto del mensaje de WhatsApp"""
    quoted_message_id: Optional[str] = None
    mentioned_jids: List[str] = []
    is_forwarded: bool = False
    forwarding_score: Optional[int] = None

class MessageData(BaseModel):
    id: str
    text: str
    from_user: str
    timestamp: datetime
    group_id: Optional[str] = None
    has_media: bool = False
    message_type: str = "text"
    quoted_message: Optional[QuotedMessage] = None
    context_info: Optional[ContextInfo] = None
    chat_type: Optional[str] = None  # 'group' | 'individual' | 'broadcast'
    participant: Optional[str] = None  # En grupos, quien envió el mensaje

class ClassificationRequest(BaseModel):
    message: MessageData

class ClassificationResponse(BaseModel):
    is_support_incident: bool
    confidence: float
    category: str  # 'technical' | 'billing' | 'general_inquiry' | 'complaint' | 'compliment' | 'not_support'
    urgency: str  # 'low' | 'medium' | 'high' | 'critical'
    summary: str
    requires_followup: bool
    suggested_response: str
    extracted_info: Dict[str, Any]
    trigger_words: List[str]
    processing_time: float = 0.0

class MessageContext(BaseModel):
    message_id: str
    sender: str
    group_id: str
    timestamp: datetime
    has_media: bool
    message_type: str

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    models_available: List[str]
    redis_connected: bool