from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class Priority(str, Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    LOW = "low"

class TicketRequest(BaseModel):
    subject: str = Field(..., description="Ticket subject")
    description: str = Field(..., description="Detailed description")
    priority: Priority = Field(default=Priority.NORMAL, description="Ticket priority")
    classification: str = Field(..., description="Request type/classification")
    contact_id: str = Field(..., description="Contact ID in Zoho")
    department_id: str = Field(..., description="Department ID in Zoho")
    
    # Optional fields
    location: Optional[str] = Field(None, description="Store/location")
    affected_system: Optional[str] = Field(None, description="System affected")
    error_messages: List[str] = Field(default=[], description="Error messages")
    attachments: List[Dict] = Field(default=[], description="File attachments")
    mentioned_users: List[str] = Field(default=[], description="@mentioned users")
    
    # Metadata
    reporter_id: str = Field(..., description="Who reports the issue")
    affected_id: Optional[str] = Field(None, description="Who is affected (if different)")
    
    # WhatsApp context
    whatsapp_message_id: Optional[str] = Field(None, description="Original WhatsApp message ID")
    group_id: Optional[str] = Field(None, description="WhatsApp group ID")

class TicketResponse(BaseModel):
    ticket_id: str
    status: str  # "created", "queued", "failed"
    message: str
    created_at: Optional[datetime] = None

class TicketStatus(BaseModel):
    ticket_id: str
    status: str
    last_updated: Optional[datetime] = None
    details: Optional[Dict] = None

class ContactRequest(BaseModel):
    email: str
    first_name: str
    last_name: Optional[str] = ""
    phone: Optional[str] = None

class ContactResponse(BaseModel):
    contact_id: str
    email: str
    name: str

class Department(BaseModel):
    id: str
    name: str
    email: Optional[str] = None