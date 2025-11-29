#!/usr/bin/env python3
"""
Setup script for Zoho OAuth authorization using UV
Run this to get your authorization code for local development
"""
import os
import sys
import subprocess
import shutil

def check_uv_installed():
    """Check if UV is installed"""
    return shutil.which('uv') is not None

def install_dependencies():
    """Install dependencies using UV"""
    try:
        print("📦 Installing dependencies with UV...")
        subprocess.run(['uv', 'sync'], check=True, cwd=os.path.dirname(__file__))
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    except FileNotFoundError:
        print("❌ UV not found. Please install UV first:")
        print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False

def main():
    print("\n🔐 Zoho OAuth Setup Helper (UV Edition)")
    print("="*50)
    
    # Check UV installation
    if not check_uv_installed():
        print("\n❌ UV is not installed. Please install it first:")
        print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("   # or")
        print("   pip install uv")
        return
    
    # Install dependencies
    if not install_dependencies():
        return
    
    # Check if .env file exists
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        print("\n⚠️  No .env file found. Creating from template...")
        
        # Check if .env.example exists
        example_path = os.path.join(os.path.dirname(__file__), '.env.example')
        if os.path.exists(example_path):
            import shutil
            shutil.copy(example_path, env_path)
            print("✅ Created .env from .env.example")
        else:
            print("❌ No .env.example found. Please create .env manually.")
            return
    
    print("\n📋 Before starting, make sure you have:")
    print("1. Created a Server-based Application in Zoho API Console")
    print("2. Set ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET in your .env file")
    
    input("\nPress Enter to continue...")
    
    print("\n🌐 Starting OAuth callback server on http://localhost:8888")
    print("\nIn your Zoho App settings, configure:")
    print("  - Homepage URL: http://localhost:8888")
    print("  - Redirect URI: http://localhost:8888/callback")
    
    print("\n" + "-"*50)
    
    # Run the auth server using UV
    try:
        auth_server_path = os.path.join(os.path.dirname(__file__), 'app', 'auth_server.py')
        subprocess.run([
            'uv', 'run', 'python', auth_server_path
        ], cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\n\n✋ Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()