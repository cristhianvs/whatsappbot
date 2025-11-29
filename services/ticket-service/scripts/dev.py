#!/usr/bin/env python3
"""
Development helper scripts for ticket service using UV
"""
import subprocess
import sys
import os

def run_service():
    """Run the ticket service with auto-reload"""
    print("🚀 Starting ticket service with UV...")
    subprocess.run([
        'uv', 'run', 'uvicorn', 
        'app.main:app', 
        '--host', '0.0.0.0', 
        '--port', '8003',
        '--reload'
    ])

def run_tests():
    """Run tests with coverage"""
    print("🧪 Running tests with UV...")
    subprocess.run([
        'uv', 'run', 'pytest', 
        'tests/', 
        '--cov=app',
        '--cov-report=html',
        '--cov-report=term-missing',
        '-v'
    ])

def setup_auth():
    """Run OAuth setup"""
    print("🔐 Starting OAuth setup...")
    subprocess.run(['uv', 'run', 'python', 'setup_zoho_auth.py'])

def format_code():
    """Format code with black"""
    print("🎨 Formatting code...")
    subprocess.run(['uv', 'run', 'black', 'app/', 'tests/', 'setup_zoho_auth.py'])

def lint_code():
    """Lint code with flake8"""
    print("🔍 Linting code...")
    subprocess.run(['uv', 'run', 'flake8', 'app/', 'tests/'])

def install_deps():
    """Install/update dependencies"""
    print("📦 Installing dependencies...")
    subprocess.run(['uv', 'sync'])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/dev.py <command>")
        print("\nAvailable commands:")
        print("  serve     - Run the service with auto-reload")
        print("  test      - Run tests with coverage")
        print("  auth      - Setup Zoho OAuth") 
        print("  format    - Format code with black")
        print("  lint      - Lint code with flake8")
        print("  install   - Install/update dependencies")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "serve":
        run_service()
    elif command == "test":
        run_tests()
    elif command == "auth":
        setup_auth()
    elif command == "format":
        format_code()
    elif command == "lint":
        lint_code()
    elif command == "install":
        install_deps()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)