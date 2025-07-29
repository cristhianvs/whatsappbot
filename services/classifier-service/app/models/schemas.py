from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ClassificationRequest(BaseModel):
    message_id: str
    text: str
    context: Optional[dict] = None
    user_id: str
    group_id: Optional[str] = None

class ClassificationResponse(BaseModel):
    is_incident: bool
    confidence: float
    category: str  # 'technical' | 'operational' | 'urgent' | 'general'
    trigger_words: List[str]
    priority: str  # 'urgent' | 'normal' | 'low'
    requires_human: bool = False

class MessageContext(BaseModel):
    previous_messages: List[str] = []
    user_history: Optional[dict] = None
    time_of_day: Optional[str] = None
    group_context: Optional[str] = None