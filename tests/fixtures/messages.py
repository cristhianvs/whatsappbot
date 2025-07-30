"""Test fixtures for WhatsApp messages and responses"""

from datetime import datetime

# Sample WhatsApp messages for testing
SUPPORT_MESSAGES = {
    "urgent_pos_failure": {
        "key": {
            "id": "test-urgent-001",
            "participant": "+573001234567@c.us",
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "conversation": "El sistema POS no funciona urgente, no podemos vender nada"
        },
        "messageTimestamp": 1640995200
    },
    
    "technical_issue": {
        "key": {
            "id": "test-tech-002",
            "participant": "+573009876543@c.us", 
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "conversation": "La aplicación se cierra sola cuando intento procesar pagos"
        },
        "messageTimestamp": 1640995260
    },
    
    "network_problem": {
        "key": {
            "id": "test-network-003",
            "participant": "+573012345678@c.us",
            "remoteJid": "120363123456@g.us", 
            "fromMe": False
        },
        "message": {
            "conversation": "No hay internet en la tienda, el sistema está offline"
        },
        "messageTimestamp": 1640995320
    },
    
    "billing_issue": {
        "key": {
            "id": "test-billing-004",
            "participant": "+573087654321@c.us",
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "conversation": "Hay un error en la factura del cliente, cobró mal"
        },
        "messageTimestamp": 1640995380
    }
}

NON_SUPPORT_MESSAGES = {
    "greeting": {
        "key": {
            "id": "test-greeting-001",
            "participant": "+573001111111@c.us",
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "conversation": "Hola, ¿cómo están todos hoy?"
        },
        "messageTimestamp": 1640995440
    },
    
    "casual_chat": {
        "key": {
            "id": "test-casual-002", 
            "participant": "+573002222222@c.us",
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "conversation": "¿Alguien sabe si hay reunión mañana?"
        },
        "messageTimestamp": 1640995500
    },
    
    "thanks": {
        "key": {
            "id": "test-thanks-003",
            "participant": "+573003333333@c.us", 
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "conversation": "Gracias por la ayuda, ya está solucionado"
        },
        "messageTimestamp": 1640995560
    }
}

MEDIA_MESSAGES = {
    "image_with_error": {
        "key": {
            "id": "test-image-001",
            "participant": "+573001234567@c.us",
            "remoteJid": "120363123456@g.us", 
            "fromMe": False
        },
        "message": {
            "imageMessage": {
                "url": "https://example.com/error-screenshot.jpg",
                "caption": "Mira este error que aparece en el POS"
            }
        },
        "messageTimestamp": 1640995620
    },
    
    "document_manual": {
        "key": {
            "id": "test-doc-002",
            "participant": "+573009876543@c.us",
            "remoteJid": "120363123456@g.us",
            "fromMe": False
        },
        "message": {
            "documentMessage": {
                "url": "https://example.com/manual.pdf",
                "filename": "manual_pos.pdf",
                "caption": "¿Alguien puede revisar este manual?"
            }
        },
        "messageTimestamp": 1640995680
    }
}

# Expected AI model responses
AI_RESPONSES = {
    "urgent_pos_failure": {
        "is_support_incident": True,
        "confidence": 0.95,
        "category": "technical", 
        "urgency": "critical",
        "summary": "Sistema POS no funciona - impide ventas",
        "requires_followup": False,
        "suggested_response": "Hemos recibido tu reporte urgente del sistema POS. Un técnico será asignado inmediatamente.",
        "extracted_info": {
            "user_type": "customer",
            "product_mentioned": "POS",
            "error_code": None,
            "contact_info": None,
            "impact": "sales_blocked"
        }
    },
    
    "technical_issue": {
        "is_support_incident": True,
        "confidence": 0.85,
        "category": "technical",
        "urgency": "high", 
        "summary": "Aplicación se cierra durante procesamiento de pagos",
        "requires_followup": True,
        "suggested_response": "Hemos registrado el problema con la aplicación. ¿Podrías indicarnos qué modelo de dispositivo estás usando?",
        "extracted_info": {
            "user_type": "customer",
            "product_mentioned": "aplicación",
            "error_code": None,
            "contact_info": None,
            "symptoms": ["crash", "payment_processing"]
        }
    },
    
    "greeting": {
        "is_support_incident": False,
        "confidence": 0.95,
        "category": "not_support",
        "urgency": "low",
        "summary": "Saludo cordial en el grupo",
        "requires_followup": False,
        "suggested_response": "¡Hola! ¿En qué podemos ayudarte hoy?",
        "extracted_info": {
            "user_type": "unknown",
            "product_mentioned": None,
            "error_code": None,
            "contact_info": None
        }
    }
}

# Expected Zoho ticket data
ZOHO_TICKETS = {
    "urgent_pos_failure": {
        "subject": "Sistema POS no funciona - impide ventas",
        "description": """
Incidente reportado desde WhatsApp:

**Resumen:** Sistema POS no funciona - impide ventas

**Categoría:** technical
**Urgencia:** critical
**Confianza:** 0.95

**Mensaje ID:** test-urgent-001
**Grupo:** 120363123456@g.us

**Información extraída:**
{
  "user_type": "customer",
  "product_mentioned": "POS",
  "impact": "sales_blocked"
}

**Respuesta sugerida:**
Hemos recibido tu reporte urgente del sistema POS. Un técnico será asignado inmediatamente.
        """.strip(),
        "priority": "urgent",
        "classification": "technical",
        "contact_id": "CONTACT-123",
        "department_id": "DEPT-456"
    }
}

# Mock Redis messages
REDIS_MESSAGES = {
    "whatsapp_inbound": {
        "id": "test-urgent-001",
        "from": "+573001234567@c.us", 
        "groupId": "120363123456@g.us",
        "text": "El sistema POS no funciona urgente, no podemos vender nada",
        "timestamp": 1640995200,
        "hasMedia": False,
        "messageType": "text",
        "rawMessage": SUPPORT_MESSAGES["urgent_pos_failure"]["message"]
    },
    
    "classification_result": {
        "message_id": "test-urgent-001",
        "group_id": "120363123456@g.us",
        "classification": AI_RESPONSES["urgent_pos_failure"],
        "timestamp": "2024-01-01T10:00:00Z"
    },
    
    "ticket_created": {
        "ticket_id": "TICKET-789",
        "group_id": "120363123456@g.us",
        "ticket_number": "#789", 
        "summary": "Sistema POS no funciona - impide ventas",
        "priority": "urgent",
        "timestamp": "2024-01-01T10:05:00Z"
    }
}

# Test user contexts
TEST_CONTEXTS = {
    "standard_user": {
        "message_id": "test-001",
        "sender": "+573001234567@c.us",
        "group_id": "120363123456@g.us",
        "timestamp": datetime.now(),
        "has_media": False,
        "message_type": "text"
    },
    
    "media_user": {
        "message_id": "test-002", 
        "sender": "+573009876543@c.us",
        "group_id": "120363123456@g.us",
        "timestamp": datetime.now(),
        "has_media": True,
        "message_type": "image"
    }
}

# Mock external API responses
MOCK_API_RESPONSES = {
    "zoho_departments": {
        "data": [
            {"id": "DEPT-001", "name": "Technical Support", "email": "tech@company.com"},
            {"id": "DEPT-002", "name": "Billing Support", "email": "billing@company.com"},
            {"id": "DEPT-003", "name": "General Support", "email": "support@company.com"}
        ]
    },
    
    "zoho_contact_created": {
        "id": "CONTACT-12345",
        "firstName": "Cliente",
        "lastName": "WhatsApp", 
        "email": "whatsapp+120363123456@support.com"
    },
    
    "zoho_ticket_created": {
        "id": "TICKET-67890",
        "ticketNumber": "67890",
        "subject": "Sistema POS no funciona",
        "statusType": "Open",
        "priority": "High"
    }
}