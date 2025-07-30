import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import httpx

from services.ticket_service.app.services.zoho_client import ZohoClient
from services.ticket_service.app.models.schemas import TicketRequest, Department


class TestZohoClient:
    """Test suite for ZohoClient"""

    @pytest.fixture
    def zoho_client(self):
        """Create ZohoClient with test configuration"""
        with patch.dict('os.environ', {
            'ZOHO_CLIENT_ID': 'test_client_id',
            'ZOHO_CLIENT_SECRET': 'test_client_secret',
            'ZOHO_REDIRECT_URI': 'http://localhost:8003/callback',
            'ZOHO_AUTHORIZATION_CODE': 'test_auth_code'
        }):
            return ZohoClient()

    @pytest.fixture
    def sample_ticket_request(self):
        """Sample ticket request for testing"""
        return TicketRequest(
            subject="Sistema POS no funciona",
            description="El sistema POS de la tienda principal está fuera de servicio",
            priority="urgent",
            classification="technical",
            contact_id="123456789",
            department_id="987654321"
        )

    @pytest.mark.asyncio
    async def test_initialization_success(self, zoho_client):
        """Test successful client initialization"""
        mock_token_response = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600
        }
        
        mock_org_response = {
            'data': [{'id': 'test_org_id'}]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.side_effect = [mock_token_response, mock_org_response]
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            await zoho_client.initialize()
            
            assert zoho_client.access_token == 'test_access_token'
            assert zoho_client.refresh_token == 'test_refresh_token'
            assert zoho_client.org_id == 'test_org_id'
            assert zoho_client.is_connected()

    @pytest.mark.asyncio
    async def test_get_tokens_from_code_success(self, zoho_client):
        """Test successful token exchange"""
        mock_response_data = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            await zoho_client._get_tokens_from_code()
            
            assert zoho_client.access_token == 'new_access_token'
            assert zoho_client.refresh_token == 'new_refresh_token'
            assert zoho_client.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_get_tokens_missing_access_token(self, zoho_client):
        """Test token exchange with missing access token"""
        mock_response_data = {
            'refresh_token': 'test_refresh_token'
            # Missing access_token
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with pytest.raises(KeyError, match="access_token not found"):
                await zoho_client._get_tokens_from_code()

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, zoho_client):
        """Test access token refresh"""
        zoho_client.refresh_token = 'existing_refresh_token'
        
        mock_response_data = {
            'access_token': 'refreshed_access_token',
            'expires_in': 3600
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            await zoho_client._refresh_access_token()
            
            assert zoho_client.access_token == 'refreshed_access_token'
            assert zoho_client.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_ensure_valid_token_refresh_needed(self, zoho_client):
        """Test token refresh when expired"""
        zoho_client.token_expires_at = datetime.now() - timedelta(minutes=1)  # Expired
        
        with patch.object(zoho_client, '_refresh_access_token') as mock_refresh:
            await zoho_client._ensure_valid_token()
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_valid_token_no_refresh_needed(self, zoho_client):
        """Test token validation when still valid"""
        zoho_client.token_expires_at = datetime.now() + timedelta(hours=1)  # Still valid
        
        with patch.object(zoho_client, '_refresh_access_token') as mock_refresh:
            await zoho_client._ensure_valid_token()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_org_id_success(self, zoho_client):
        """Test successful organization ID retrieval"""
        zoho_client.access_token = 'test_token'
        
        mock_response_data = {
            'data': [
                {'id': 'org_123', 'name': 'Test Organization'}
            ]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            await zoho_client._get_org_id()
            
            assert zoho_client.org_id == 'org_123'

    @pytest.mark.asyncio
    async def test_get_org_id_no_organizations(self, zoho_client):
        """Test organization ID retrieval with no organizations"""
        zoho_client.access_token = 'test_token'
        
        mock_response_data = {'data': []}

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            with pytest.raises(ValueError, match="No organizations found"):
                await zoho_client._get_org_id()

    @pytest.mark.asyncio
    async def test_list_departments_success(self, zoho_client):
        """Test successful department listing"""
        zoho_client.access_token = 'test_token'
        zoho_client.org_id = 'test_org'
        
        mock_response_data = {
            'data': [
                {'id': 'dept_1', 'name': 'Technical Support', 'email': 'tech@example.com'},
                {'id': 'dept_2', 'name': 'Billing', 'email': 'billing@example.com'}
            ]
        }

        with patch.object(zoho_client, '_make_request') as mock_request:
            mock_request.return_value = mock_response_data
            
            departments = await zoho_client.list_departments()
            
            assert len(departments) == 2
            assert isinstance(departments[0], Department)
            assert departments[0].id == 'dept_1'
            assert departments[0].name == 'Technical Support'
            assert departments[0].email == 'tech@example.com'

    @pytest.mark.asyncio
    async def test_create_contact_success(self, zoho_client):
        """Test successful contact creation"""
        mock_response_data = {'id': 'contact_123'}

        with patch.object(zoho_client, '_make_request') as mock_request:
            mock_request.return_value = mock_response_data
            
            contact_id = await zoho_client.create_contact('test@example.com', 'John Doe')
            
            assert contact_id == 'contact_123'
            mock_request.assert_called_once_with(
                'POST', 
                '/contacts',
                json={
                    'firstName': 'John',
                    'lastName': 'Doe',
                    'email': 'test@example.com'
                }
            )

    @pytest.mark.asyncio
    async def test_create_contact_single_name(self, zoho_client):
        """Test contact creation with single name"""
        mock_response_data = {'id': 'contact_456'}

        with patch.object(zoho_client, '_make_request') as mock_request:
            mock_request.return_value = mock_response_data
            
            contact_id = await zoho_client.create_contact('test@example.com', 'John')
            
            assert contact_id == 'contact_456'
            mock_request.assert_called_once_with(
                'POST', 
                '/contacts',
                json={
                    'firstName': 'John',
                    'lastName': '',
                    'email': 'test@example.com'
                }
            )

    @pytest.mark.asyncio
    async def test_create_ticket_success(self, zoho_client, sample_ticket_request):
        """Test successful ticket creation"""
        mock_response_data = {'id': 'ticket_789'}

        with patch.object(zoho_client, '_make_request') as mock_request:
            mock_request.return_value = mock_response_data
            
            ticket_id = await zoho_client.create_ticket(sample_ticket_request)
            
            assert ticket_id == 'ticket_789'
            
            # Verify request payload
            call_args = mock_request.call_args
            assert call_args[0][0] == 'POST'
            assert call_args[0][1] == '/tickets'
            
            payload = call_args[1]['json']
            assert payload['subject'] == sample_ticket_request.subject
            assert payload['description'] == sample_ticket_request.description
            assert payload['priority'] == 'High'  # urgent -> High
            assert payload['departmentId'] == sample_ticket_request.department_id
            assert payload['contactId'] == sample_ticket_request.contact_id

    @pytest.mark.asyncio
    async def test_create_ticket_priority_mapping(self, zoho_client):
        """Test ticket priority mapping"""
        test_cases = [
            ('urgent', 'High'),
            ('normal', 'Medium'),
            ('low', 'Low')
        ]

        for priority_in, priority_out in test_cases:
            ticket_request = TicketRequest(
                subject="Test",
                description="Test description",
                priority=priority_in,
                classification="technical",
                contact_id="123",
                department_id="456"
            )

            with patch.object(zoho_client, '_make_request') as mock_request:
                mock_request.return_value = {'id': 'test_ticket'}
                
                await zoho_client.create_ticket(ticket_request)
                
                payload = mock_request.call_args[1]['json']
                assert payload['priority'] == priority_out

    @pytest.mark.asyncio
    async def test_get_ticket_status_success(self, zoho_client):
        """Test successful ticket status retrieval"""
        mock_response_data = {'statusType': 'Open'}

        with patch.object(zoho_client, '_make_request') as mock_request:
            mock_request.return_value = mock_response_data
            
            status = await zoho_client.get_ticket_status('ticket_123')
            
            assert status == 'Open'
            mock_request.assert_called_once_with('GET', '/tickets/ticket_123')

    @pytest.mark.asyncio
    async def test_update_ticket_success(self, zoho_client):
        """Test successful ticket update"""
        updates = {'status': 'In Progress', 'assigneeId': 'agent_123'}
        mock_response_data = {'id': 'ticket_123', 'status': 'In Progress'}

        with patch.object(zoho_client, '_make_request') as mock_request:
            mock_request.return_value = mock_response_data
            
            result = await zoho_client.update_ticket('ticket_123', updates)
            
            assert result == mock_response_data
            mock_request.assert_called_once_with('PATCH', '/tickets/ticket_123', json=updates)

    def test_generate_authorization_url(self, zoho_client):
        """Test authorization URL generation"""
        url = zoho_client.generate_authorization_url()
        
        assert 'accounts.zoho.com/oauth/v2/auth' in url
        assert 'response_type=code' in url
        assert 'client_id=test_client_id' in url
        assert 'redirect_uri=http://localhost:8003/callback' in url
        assert 'scope=' in url

    def test_is_connected_true(self, zoho_client):
        """Test connection status when properly connected"""
        zoho_client.access_token = 'test_token'
        zoho_client.org_id = 'test_org'
        
        assert zoho_client.is_connected() is True

    def test_is_connected_false(self, zoho_client):
        """Test connection status when not connected"""
        assert zoho_client.is_connected() is False

    @pytest.mark.asyncio
    async def test_make_request_with_auth_headers(self, zoho_client):
        """Test _make_request includes proper authentication headers"""
        zoho_client.access_token = 'test_token'
        zoho_client.org_id = 'test_org'
        zoho_client.token_expires_at = datetime.now() + timedelta(hours=1)
        
        mock_response = {'data': 'test'}

        with patch('httpx.AsyncClient') as mock_client:
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = mock_response
            mock_http_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_http_response
            
            result = await zoho_client._make_request('GET', '/test')
            
            assert result == mock_response
            
            # Verify headers were set correctly
            call_args = mock_client.return_value.__aenter__.return_value.get.call_args
            headers = call_args[1]['headers']
            assert headers['Authorization'] == 'Zoho-oauthtoken test_token'
            assert headers['orgId'] == 'test_org'
            assert headers['Content-Type'] == 'application/json'