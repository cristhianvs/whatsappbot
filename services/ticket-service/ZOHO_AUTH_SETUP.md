# Zoho OAuth Setup Guide

This guide helps you set up Zoho OAuth authentication for **long-term development** access.

## Prerequisites

1. Zoho account with Zoho Desk access
2. Python 3.9+ installed
3. UV package manager installed: https://docs.astral.sh/uv/
4. Access to Zoho API Console: https://api-console.zoho.com/

### Install UV (if not already installed)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

## Step 1: Create Zoho Server-based Application

⚠️ **Important**: Use **Server-based Application**, NOT Self Client, for long-term tokens.

1. Go to [Zoho API Console](https://api-console.zoho.com/)
2. Click on **"Add Client"** 
3. Choose **"Server-based Applications"** (this provides permanent refresh tokens)
4. Fill in the details:
   - **Client Name**: `WhatsApp Support Bot`
   - **Client Domain**: `localhost`
   - **Homepage URL**: `http://localhost:8888`
   - **Authorized Redirect URIs**: `http://localhost:8888/callback`
5. Click "Create"
6. Save your **Client ID** and **Client Secret**

### Why Server-based vs Self Client?
- **Server-based**: ✅ Permanent refresh tokens, automatic renewal
- **Self Client**: ❌ Tokens expire every 10 minutes, not suitable for development

## Step 2: Configure Environment

1. Copy the example environment file:
```bash
cd services/ticket-service
cp .env.example .env
```

2. Edit `.env` and add your Zoho credentials:
```env
ZOHO_CLIENT_ID=1000.XXXXXXXXXX
ZOHO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxx
ZOHO_REDIRECT_URI=http://localhost:8888/callback
```

## Step 3: Get Authorization Code

### Option A: Using the Auth Helper (Recommended)

1. Run the UV-powered setup script:
```bash
cd services/ticket-service
uv run python setup_zoho_auth.py
```
This automatically installs dependencies and starts the OAuth server.

2. Your browser will open automatically to `http://localhost:8888`

3. Click "Start Authorization"

4. Login to Zoho and approve the permissions

5. Copy the authorization code from the success page

6. Add it to your `.env` file:
```env
ZOHO_AUTHORIZATION_CODE=1000.xxxxxxxxxx.xxxxxxxxxx
```

### Option B: Manual UV Commands

1. Install dependencies:
```bash
cd services/ticket-service
uv sync
```

2. Start the auth server manually:
```bash
uv run python app/auth_server.py
```

3. Follow the browser instructions

### Option C: Using the API Endpoint

1. Start the ticket service:
```bash
# With Docker
docker-compose up ticket-service

# Or with UV
cd services/ticket-service
uv run uvicorn app.main:app --host 0.0.0.0 --port 8003
```

2. Get the authorization URL:
```bash
curl http://localhost:8003/auth/url
```

3. Visit the URL, authorize, and copy the code from the redirect URL

### Option D: Manual URL Generation

1. Construct the URL manually:
```
https://accounts.zoho.com/oauth/v2/auth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8888/callback&scope=Desk.tickets.ALL,Desk.contacts.ALL,Desk.basic.ALL&access_type=offline&prompt=consent
```

2. Replace `YOUR_CLIENT_ID` with your actual client ID

## Step 4: Start the Service

Once you have the authorization code in your `.env` file:

```bash
# Restart the service to use the new code
docker-compose restart ticket-service

# Check if it's working
curl http://localhost:8003/health
```

## Important Notes

⚠️ **Authorization codes expire in ~10 minutes!** The service will exchange it for a long-lived refresh token on first start.

✅ **The refresh token is permanent** - Once the service successfully exchanges the code, it will store the refresh token in `.zoho_tokens.json` for future use.

🔄 **Automatic token refresh** - The service automatically refreshes the access token when it expires (every hour).

💾 **Token persistence** - After first setup, the service will automatically reuse saved tokens. You only need to get the authorization code **once**.

## Troubleshooting

### "Invalid authorization code"
- The code has expired (>10 minutes old)
- The code was already used
- Solution: Generate a new code using the steps above

### "No organizations found"
- The Zoho account doesn't have access to Zoho Desk
- Solution: Ensure Zoho Desk is enabled for your account

### Connection refused on localhost:8888
- The auth helper server isn't running
- Solution: Run `python setup_zoho_auth.py` first

## Required Scopes

The application requests these Zoho Desk scopes:
- `ZohoDesk.tickets.ALL` - Create, read, update tickets
- `ZohoDesk.contacts.ALL` - Manage contacts  
- `ZohoDesk.basic.ALL` - Access departments and basic data
- `ZohoDesk.search.READ` - Search existing records

## Security Notes

- Never commit your `.env` file with real credentials
- The refresh token provides permanent access - keep it secure
- In production, use proper HTTPS URLs for redirects