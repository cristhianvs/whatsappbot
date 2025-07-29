import httpx
import os
import time
import structlog
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..models.schemas import TicketRequest, Department

logger = structlog.get_logger()

class ZohoClient:
    def __init__(self):
        self.client_id = os.getenv('ZOHO_CLIENT_ID')
        self.client_secret = os.getenv('ZOHO_CLIENT_SECRET')
        self.redirect_uri = os.getenv('ZOHO_REDIRECT_URI')
        self.authorization_code = os.getenv('ZOHO_AUTHORIZATION_CODE')
        
        self.access_token = None
        self.refresh_token = None
        self.org_id = None
        self.token_expires_at = None
        
        self.base_url = 'https://desk.zoho.com/api/v1'
        self.auth_url = 'https://accounts.zoho.com/oauth/v2'
        
    async def initialize(self):
        """Initialize Zoho client with tokens and org ID"""
        try:
            # Get initial tokens
            await self._get_tokens_from_code()
            
            # Get organization ID
            await self._get_org_id()
            
            logger.info("Zoho client initialized", org_id=self.org_id)
            
        except Exception as e:
            logger.error("Failed to initialize Zoho client", error=str(e))
            raise
    
    def is_connected(self) -> bool:
        """Check if client is properly connected"""
        return bool(self.access_token and self.org_id)
    
    async def _get_tokens_from_code(self):
        """Exchange authorization code for access and refresh tokens"""
        async with httpx.AsyncClient() as client:
            data = {
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'code': self.authorization_code
            }
            
            response = await client.post(f"{self.auth_url}/token", data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            if 'access_token' not in token_data:
                raise KeyError("access_token not found in response")
            
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            
            # Set token expiration (typically 1 hour)
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 min buffer
            
            logger.info("Tokens obtained successfully")
    
    async def _refresh_access_token(self):
        """Refresh the access token using refresh token"""
        async with httpx.AsyncClient() as client:
            params = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = await client.post(f"{self.auth_url}/token", params=params)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            
            # Update expiration
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            
            logger.info("Access token refreshed")
    
    async def _ensure_valid_token(self):
        """Ensure we have a valid access token"""
        if not self.token_expires_at or datetime.now() >= self.token_expires_at:
            await self._refresh_access_token()
    
    async def _get_org_id(self):
        """Get the organization ID"""
        await self._ensure_valid_token()
        
        async with httpx.AsyncClient() as client:
            headers = {'Authorization': f'Zoho-oauthtoken {self.access_token}'}
            
            response = await client.get(f"{self.base_url}/organizations", headers=headers)
            response.raise_for_status()
            
            data = response.json().get('data', [])
            if not data:
                raise ValueError("No organizations found")
            
            self.org_id = data[0]['id']
    
    async def _make_request(self, method: str, endpoint: str, **kwargs):
        """Make authenticated request to Zoho API"""
        await self._ensure_valid_token()
        
        headers = {
            'Authorization': f'Zoho-oauthtoken {self.access_token}',
            'orgId': str(self.org_id),
            'Content-Type': 'application/json'
        }
        
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        async with httpx.AsyncClient() as client:
            response = await getattr(client, method.lower())(
                f"{self.base_url}{endpoint}", 
                **kwargs
            )
            response.raise_for_status()
            return response.json()
    
    async def list_departments(self) -> List[Department]:
        """List all departments"""
        try:
            data = await self._make_request('GET', '/departments')
            departments = data.get('data', [])
            
            return [
                Department(
                    id=dept['id'],
                    name=dept['name'],
                    email=dept.get('email')
                )
                for dept in departments
            ]
            
        except Exception as e:
            logger.error("Failed to list departments", error=str(e))
            raise
    
    async def create_contact(self, email: str, name: str = 'Cliente Prueba') -> str:
        """Create a contact in Zoho Desk"""
        try:
            payload = {
                'firstName': name.split()[0] if ' ' in name else name,
                'lastName': name.split()[1] if ' ' in name else '',
                'email': email
            }
            
            data = await self._make_request('POST', '/contacts', json=payload)
            contact_id = data['id']
            
            logger.info("Contact created", contact_id=contact_id, email=email)
            return contact_id
            
        except Exception as e:
            logger.error("Failed to create contact", error=str(e), email=email)
            raise
    
    async def create_ticket(self, ticket_request: TicketRequest) -> str:
        """Create a ticket in Zoho Desk"""
        try:
            payload = {
                'subject': ticket_request.subject,
                'description': ticket_request.description,
                'departmentId': ticket_request.department_id,
                'contactId': ticket_request.contact_id,
                'classification': ticket_request.classification
            }
            
            # Set priority based on our enum
            if ticket_request.priority.value == 'urgent':
                payload['priority'] = 'High'
            elif ticket_request.priority.value == 'normal':
                payload['priority'] = 'Medium'
            else:
                payload['priority'] = 'Low'
            
            # Add optional fields if present
            if ticket_request.location:
                payload['cf_location'] = ticket_request.location  # Custom field
            
            data = await self._make_request('POST', '/tickets', json=payload)
            ticket_id = data.get('id') or data.get('ticketId')
            
            logger.info(
                "Ticket created in Zoho",
                ticket_id=ticket_id,
                subject=ticket_request.subject,
                priority=ticket_request.priority.value
            )
            
            return str(ticket_id)
            
        except Exception as e:
            logger.error("Failed to create ticket", error=str(e))
            raise
    
    async def get_ticket_status(self, ticket_id: str) -> str:
        """Get ticket status from Zoho"""
        try:
            data = await self._make_request('GET', f'/tickets/{ticket_id}')
            return data.get('statusType', 'Unknown')
            
        except Exception as e:
            logger.error("Failed to get ticket status", error=str(e), ticket_id=ticket_id)
            raise
    
    async def update_ticket(self, ticket_id: str, updates: Dict) -> Dict:
        """Update a ticket in Zoho"""
        try:
            data = await self._make_request('PATCH', f'/tickets/{ticket_id}', json=updates)
            
            logger.info("Ticket updated", ticket_id=ticket_id, updates=updates)
            return data
            
        except Exception as e:
            logger.error("Failed to update ticket", error=str(e), ticket_id=ticket_id)
            raise
    
    def generate_authorization_url(self) -> str:
        """Generate URL for obtaining new authorization code"""
        base_url = f'{self.auth_url}/auth'
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'Desk.tickets.CREATE,Desk.contacts.CREATE,Desk.basic.READ'
        }
        
        url = f"{base_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        return url