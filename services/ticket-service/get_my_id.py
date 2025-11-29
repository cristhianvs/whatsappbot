#!/usr/bin/env python3
"""
Get or create contact ID for cvelazco@turistore.com
"""
import requests
import json

BASE_URL = "http://localhost:8005"

def get_my_contact_id():
    """Get contact ID for cvelazco@turistore.com"""
    email = "cvelazco@turistore.com"
    name = "Cristhian Velazco"
    
    print(f"Getting contact ID for: {email}")
    
    # Step 1: Try to search
    print("\n1. Searching for existing contact...")
    try:
        response = requests.get(f"{BASE_URL}/contacts/search?email={email}")
        print(f"Search status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Search result: {json.dumps(result, indent=2)}")
            
            if result.get('found'):
                contact_id = result.get('contact_id')
                print(f"\n✅ Found your existing contact ID: {contact_id}")
                save_config(email, contact_id, name)
                return contact_id
                
    except Exception as e:
        print(f"Search error: {e}")
    
    # Step 2: Try to create (might already exist)
    print(f"\n2. Attempting to create contact...")
    try:
        response = requests.post(f"{BASE_URL}/contacts?email={email}&name={name}")
        print(f"Create status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Create result: {json.dumps(result, indent=2)}")
            
            contact_id = result.get('contact_id')
            if contact_id:
                print(f"\n✅ Your contact ID: {contact_id}")
                save_config(email, contact_id, name)
                return contact_id
        else:
            print(f"Create failed: {response.text}")
            
    except Exception as e:
        print(f"Create error: {e}")
    
    print("\n❌ Could not determine your contact ID")
    return None

def save_config(email, contact_id, name):
    """Save contact configuration"""
    config = {
        "default_contact": {
            "email": email,
            "contact_id": contact_id,
            "name": name
        },
        "usage": {
            "description": "Use this contact_id for all tickets created by the system",
            "example": f"contact_id: '{contact_id}'"
        }
    }
    
    try:
        with open("default_contact.json", "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"\n💾 Saved configuration to default_contact.json")
        print(f"📋 Your contact ID: {contact_id}")
        print(f"📧 Email: {email}")
        print(f"👤 Name: {name}")
        
    except Exception as e:
        print(f"Failed to save config: {e}")

def test_ticket_with_my_id():
    """Test creating a ticket with your contact ID"""
    try:
        with open("default_contact.json", "r") as f:
            config = json.load(f)
        
        contact_id = config["default_contact"]["contact_id"]
        print(f"\n🎫 Testing ticket creation with your contact ID: {contact_id}")
        
        test_data = {
            "subject": "Test with My Contact ID",
            "description": "Testing ticket creation with my personal contact ID",
            "priority": "High",
            "contact_id": contact_id,
            "department_id": "813934000000006907",  # Soporte TI
            "classification": "Problem"
        }
        
        response = requests.post(f"{BASE_URL}/tickets", json=test_data)
        print(f"Ticket creation status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ticket created successfully!")
            print(f"   Ticket ID: {result.get('ticket_id')}")
            print(f"   Status: {result.get('status')}")
        else:
            print(f"❌ Ticket creation failed: {response.text}")
            
    except FileNotFoundError:
        print("❌ Configuration file not found. Run the contact ID lookup first.")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    contact_id = get_my_contact_id()
    
    if contact_id:
        print(f"\n" + "="*50)
        test_ticket_with_my_id()