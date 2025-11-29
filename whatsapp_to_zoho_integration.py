#!/usr/bin/env python3
"""
Real-time WhatsApp to Zoho Desk Integration
Monitors WhatsApp messages and creates tickets automatically
"""
import redis
import json
import requests
import time
from datetime import datetime

# Service configuration
TICKET_SERVICE_URL = "http://localhost:8005"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# Technical keywords for classification
TECHNICAL_KEYWORDS = ['impresora', 'sistema', 'pos', 'computadora', 'servidor', 'error', 
                     'no funciona', 'ayuda', 'urgente', 'problema', 'falla']

def classify_message(text):
    """Simple keyword-based classification"""
    text_lower = text.lower()
    
    # Check if message contains technical keywords
    is_technical = any(keyword in text_lower for keyword in TECHNICAL_KEYWORDS)
    
    if is_technical:
        # Determine priority
        priority = 'High' if any(word in text_lower for word in ['urgente', 'critico', 'no funciona']) else 'Medium'
        
        return {
            'is_incident': True,
            'category': 'technical',
            'priority': priority,
            'confidence': 0.9
        }
    
    return {'is_incident': False}

def create_ticket_from_whatsapp(message_data):
    """Create a Zoho ticket from WhatsApp message data"""
    try:
        # Parse message data
        data = json.loads(message_data) if isinstance(message_data, str) else message_data
        
        # Extract message info
        text = data.get('text', '')
        sender = data.get('from', 'unknown')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        message_id = data.get('id', 'unknown')
        
        print(f"\nProcessing WhatsApp message:")
        print(f"  From: {sender}")
        print(f"  Text: {text}")
        print(f"  ID: {message_id}")
        
        # Classify the message
        classification = classify_message(text)
        
        if not classification['is_incident']:
            print("  -> Not classified as support incident, skipping")
            return None
        
        print(f"  -> Classified as: {classification['category']} incident, Priority: {classification['priority']}")
        
        # Extract phone number from sender
        phone = sender.replace('@s.whatsapp.net', '').replace('@c.us', '')
        customer_email = f"{phone}@whatsapp.support.com"
        customer_name = f"WhatsApp User {phone[-4:]}"
        
        # Create ticket description
        description = f"""
Mensaje recibido via WhatsApp:
"{text}"

Informacion del remitente:
- Telefono: {phone}
- Timestamp: {timestamp}
- Message ID: {message_id}

Clasificacion automatica:
- Categoria: {classification['category']}
- Prioridad: {classification['priority']}
- Confianza: {classification['confidence']}

Canal: WhatsApp Bot Real-Time
        """.strip()
        
        # Prepare ticket data
        ticket_data = {
            "customer_email": customer_email,
            "customer_name": customer_name,
            "subject": f"Incidente {classification['category']} - WhatsApp",
            "description": description,
            "priority": classification['priority']
        }
        
        print("\nCreating ticket in Zoho Desk...")
        
        # Call ticket service
        response = requests.post(
            f"{TICKET_SERVICE_URL}/tickets/customer",
            params=ticket_data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nSUCCESS! Ticket created automatically!")
            print(f"   Ticket ID: {result.get('ticket_id')}")
            print(f"   Contact ID: {result.get('contact_id')}")
            print(f"   Customer: {customer_email}")
            print("-" * 60)
            return result
        else:
            print(f"\nFailed to create ticket: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"\nError processing message: {e}")
        return None

def monitor_whatsapp_messages():
    """Monitor Redis for WhatsApp messages and create tickets"""
    print("WhatsApp to Zoho Integration Started")
    print("=" * 60)
    print("Monitoring WhatsApp messages in real-time...")
    print("Send a message with keywords like: impresora, error, urgente, ayuda")
    print("-" * 60)
    
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    # Subscribe to WhatsApp messages
    pubsub = r.pubsub()
    pubsub.subscribe('whatsapp:messages:inbound')
    
    try:
        # Listen for messages
        for message in pubsub.listen():
            if message['type'] == 'message':
                print(f"\nNew WhatsApp message received!")
                create_ticket_from_whatsapp(message['data'])
                
    except KeyboardInterrupt:
        print("\n\nIntegration stopped by user")
    finally:
        pubsub.close()
        r.close()

if __name__ == "__main__":
    monitor_whatsapp_messages()