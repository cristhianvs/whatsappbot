"""
Local OAuth callback server for Zoho authorization
This server helps capture the authorization code during development
"""
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import webbrowser
import os
from datetime import datetime
import structlog
from dotenv import load_dotenv

# Load environment variables from .env file in parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logger = structlog.get_logger()

app = FastAPI(title="Zoho OAuth Callback Server")

# Store the authorization code when received
authorization_code = None
auth_timestamp = None

@app.get("/")
async def home():
    """Homepage for Zoho OAuth setup"""
    return HTMLResponse(content="""
    <html>
        <head>
            <title>Zoho OAuth Setup</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .step { background: #f0f0f0; padding: 20px; margin: 20px 0; border-radius: 8px; }
                .code { background: #333; color: #0f0; padding: 10px; font-family: monospace; }
                button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Zoho OAuth Setup Helper</h1>
                
                <div class="step">
                    <h2>Step 1: Configure Zoho App</h2>
                    <p>In your Zoho API Console, set these values:</p>
                    <ul>
                        <li><strong>Homepage URL:</strong> <code>http://localhost:8888</code></li>
                        <li><strong>Authorized Redirect URI:</strong> <code>http://localhost:8888/callback</code></li>
                    </ul>
                </div>
                
                <div class="step">
                    <h2>Step 2: Get Authorization URL</h2>
                    <p>Click the button below to generate and open the authorization URL:</p>
                    <button onclick="window.location.href='/authorize'">Start Authorization</button>
                </div>
                
                <div class="step">
                    <h2>Step 3: Check Status</h2>
                    <p>After authorizing, check if we received the code:</p>
                    <button onclick="window.location.href='/status'">Check Status</button>
                </div>
            </div>
        </body>
    </html>
    """)

@app.get("/callback")
async def oauth_callback(code: str = None, error: str = None):
    """Handle OAuth callback from Zoho"""
    global authorization_code, auth_timestamp
    
    if error:
        return HTMLResponse(content=f"""
        <html>
            <head><title>Authorization Failed</title></head>
            <body style="font-family: Arial; margin: 40px;">
                <h1 style="color: red;">Authorization Failed</h1>
                <p>Error: {error}</p>
                <a href="/">Go Back</a>
            </body>
        </html>
        """)
    
    if code:
        authorization_code = code
        auth_timestamp = datetime.now()
        
        # Save to .env file
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        
        return HTMLResponse(content=f"""
        <html>
            <head>
                <title>Authorization Successful!</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .success {{ background: #d4edda; border: 1px solid #c3e6cb; padding: 20px; border-radius: 4px; }}
                    .code {{ background: #f8f9fa; padding: 10px; font-family: monospace; word-break: break-all; }}
                    .warning {{ background: #fff3cd; border: 1px solid #ffeeba; padding: 15px; margin: 20px 0; border-radius: 4px; }}
                </style>
            </head>
            <body>
                <div class="success">
                    <h1>✅ Authorization Successful!</h1>
                    <p>Authorization code received at {auth_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                <h2>Your Authorization Code:</h2>
                <div class="code">{code}</div>
                
                <div class="warning">
                    <h3>⚠️ Important:</h3>
                    <ul>
                        <li>This code expires in ~10 minutes</li>
                        <li>Add this to your <code>.env</code> file:</li>
                    </ul>
                    <div class="code">ZOHO_AUTHORIZATION_CODE={code}</div>
                </div>
                
                <h2>Next Steps:</h2>
                <ol>
                    <li>Copy the authorization code above</li>
                    <li>Update your <code>services/ticket-service/.env</code> file</li>
                    <li>Restart the ticket service: <code>docker-compose restart ticket-service</code></li>
                    <li>The service will exchange this code for long-lived refresh token</li>
                </ol>
                
                <p><a href="/status">Check Token Status</a> | <a href="/">Home</a></p>
            </body>
        </html>
        """)
    
    return HTMLResponse(content="""
    <html>
        <head><title>No Authorization Code</title></head>
        <body style="font-family: Arial; margin: 40px;">
            <h1>No Authorization Code Received</h1>
            <a href="/">Go Back</a>
        </body>
    </html>
    """)

@app.get("/authorize")
async def start_authorization():
    """Generate and redirect to Zoho authorization URL"""
    # Read config from environment or use defaults
    client_id = os.getenv('ZOHO_CLIENT_ID')
    
    if not client_id:
        return HTMLResponse(content="""
        <html>
            <body style="font-family: Arial; margin: 40px;">
                <h1 style="color: red;">Configuration Error</h1>
                <p>ZOHO_CLIENT_ID not found in environment variables.</p>
                <p>Please set up your .env file first.</p>
                <a href="/">Go Back</a>
            </body>
        </html>
        """)
    
    # Generate authorization URL
    auth_base_url = "https://accounts.zoho.com/oauth/v2/auth"
    redirect_uri = "http://localhost:8888/callback"
    scope = "Desk.tickets.ALL,Desk.contacts.ALL,Desk.basic.ALL"
    
    auth_url = (
        f"{auth_base_url}"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    
    # Open in browser
    logger.info("Opening authorization URL in browser", url=auth_url)
    webbrowser.open(auth_url)
    
    return HTMLResponse(content=f"""
    <html>
        <head>
            <title>Redirecting to Zoho...</title>
            <meta http-equiv="refresh" content="0; url={auth_url}">
        </head>
        <body style="font-family: Arial; margin: 40px;">
            <h1>Redirecting to Zoho...</h1>
            <p>If you're not redirected automatically, <a href="{auth_url}">click here</a>.</p>
        </body>
    </html>
    """)

@app.get("/status")
async def check_status():
    """Check current authorization status"""
    global authorization_code, auth_timestamp
    
    status_html = """
    <html>
        <head>
            <title>Authorization Status</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .status { padding: 20px; border-radius: 4px; margin: 20px 0; }
                .success { background: #d4edda; border: 1px solid #c3e6cb; }
                .pending { background: #fff3cd; border: 1px solid #ffeeba; }
                .code { background: #f8f9fa; padding: 10px; font-family: monospace; word-break: break-all; }
            </style>
        </head>
        <body>
            <h1>Authorization Status</h1>
    """
    
    if authorization_code:
        time_diff = (datetime.now() - auth_timestamp).seconds
        expired = time_diff > 600  # 10 minutes
        
        status_html += f"""
            <div class="status success">
                <h2>✅ Authorization Code Received</h2>
                <p>Received at: {auth_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Age: {time_diff} seconds {"(EXPIRED)" if expired else "(still valid)"}</p>
                <div class="code">{authorization_code}</div>
            </div>
        """
    else:
        status_html += """
            <div class="status pending">
                <h2>⏳ No Authorization Code Yet</h2>
                <p>Please complete the authorization flow first.</p>
            </div>
        """
    
    status_html += """
            <p><a href="/">Back to Home</a></p>
        </body>
    </html>
    """
    
    return HTMLResponse(content=status_html)

@app.get("/env-template")
async def get_env_template():
    """Generate .env template with current values"""
    template = f"""# Zoho Desk Configuration
ZOHO_CLIENT_ID=your_client_id_here
ZOHO_CLIENT_SECRET=your_client_secret_here
ZOHO_REDIRECT_URI=http://localhost:8888/callback
ZOHO_AUTHORIZATION_CODE={authorization_code or 'get_from_auth_flow'}

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Service Configuration
PORT=8003
HOST=0.0.0.0
ENVIRONMENT=development
"""
    
    return HTMLResponse(
        content=f"<pre>{template}</pre>",
        media_type="text/plain"
    )

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Zoho OAuth Setup Server")
    print("="*60)
    print("\nStarting local server for Zoho OAuth configuration...")
    print("\n📋 Add these to your Zoho App configuration:")
    print("   Homepage URL: http://localhost:8888")
    print("   Redirect URI: http://localhost:8888/callback")
    print("\n🌐 Opening browser to: http://localhost:8888")
    print("\n✋ Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Open browser automatically
    webbrowser.open("http://localhost:8888")
    
    # Run server
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")