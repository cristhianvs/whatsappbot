#!/usr/bin/env python3
"""
Test the proper customer contact workflow
"""
import requests
import json

BASE_URL = "http://localhost:8005"

def test_customer_workflow():
    """Test creating tickets for different customers"""
    
    # Test Case 1: New customer
    print("🧪 Test Case 1: New Customer")
    print("="*50)
    
    new_customer = {
        "customer_email": "juan.perez@empresa.com",
        "customer_name": "Juan Perez",
        "subject": "Impresora no funciona",
        "description": "La impresora HP en la oficina 205 no imprime documentos",
        "priority": "High"
    }
    
    test_customer_ticket(new_customer, "New customer (should create contact)")
    
    print("\n" + "="*50)
    
    # Test Case 2: Existing customer (you)
    print("🧪 Test Case 2: Existing Customer")
    print("="*50)
    
    existing_customer = {
        "customer_email": "cvelazco@turistore.com",
        "customer_name": "Cristhian Velazco",
        "subject": "Problema con el sistema",
        "description": "El sistema CRM no está sincronizando correctamente",
        "priority": "Medium"
    }
    
    test_customer_ticket(existing_customer, "Existing customer (should reuse contact)")
    
    print("\n" + "="*50)
    
    # Test Case 3: Another new customer
    print("🧪 Test Case 3: Another New Customer")
    print("="*50)
    
    another_customer = {
        "customer_email": "maria.gonzalez@cliente.com",
        "customer_name": "Maria Gonzalez",
        "subject": "Consulta sobre facturación",
        "description": "Necesito información sobre mi última factura",
        "priority": "Low"
    }
    
    test_customer_ticket(another_customer, "Another new customer")

def test_customer_ticket(customer_data, test_description):
    """Test creating a ticket for a specific customer"""
    print(f"📝 {test_description}")
    print(f"📧 Customer: {customer_data['customer_name']} ({customer_data['customer_email']})")
    print(f"🎫 Subject: {customer_data['subject']}")
    
    try:
        # Create ticket using the customer workflow endpoint
        response = requests.post(
            f"{BASE_URL}/tickets/customer",
            params=customer_data
        )
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS!")
            print(f"   🎫 Ticket ID: {result.get('ticket_id')}")
            print(f"   👤 Contact ID: {result.get('contact_id')}")
            print(f"   📧 Customer Email: {result.get('customer_email')}")
            print(f"   📝 Message: {result.get('message')}")
            
            # Show what happened in Zoho
            contact_id = result.get('contact_id')
            if contact_id:
                print(f"   🔍 Contact created/found for: {customer_data['customer_email']}")
                print(f"   📞 This customer can be reached at their email for updates")
                
        else:
            print(f"❌ FAILED: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def show_workflow_explanation():
    """Explain how the proper workflow should work"""
    print("\n🤖 WhatsApp Bot Workflow (Phase 2 Implementation)")
    print("="*60)
    print("""
1. 📱 User sends WhatsApp message: "Mi impresora no funciona"

2. 🤖 Bot classifies message → Detects support incident

3. 💬 Bot asks: "Hola! Para crear tu ticket de soporte, 
   necesito tu email para darte seguimiento."

4. 👤 User responds: "juan.perez@empresa.com"

5. 🔍 System searches Zoho for existing contact

6. 📝 System creates ticket under Juan's contact (not yours!)

7. 📧 Juan receives email: "Ticket #12345 creado. Te contactaremos pronto."

8. 🎯 You (as support agent) see ticket assigned to correct customer
    """)
    
    print("\n🚫 Current Problem:")
    print("   - All tickets created under your contact (cvelazco@turistore.com)")
    print("   - Customers don't get proper notifications")
    print("   - Can't track individual customer history")
    
    print("\n✅ Solution:")
    print("   - Implement conversation service to collect customer email")
    print("   - Use get_or_create_contact() for each customer")
    print("   - Create tickets under actual customer contacts")

if __name__ == "__main__":
    print("🧪 Testing Customer Contact Workflow")
    print("="*60)
    
    test_customer_workflow()
    show_workflow_explanation()