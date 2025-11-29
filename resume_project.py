#!/usr/bin/env python3
"""
Project Resume Command - WhatsApp Support Bot

This script provides a comprehensive overview of the current project status
and prepares the development environment for continuing work.

Usage:
    python resume_project.py [--verbose] [--check-services] [--start-services]
"""

import os
import sys
import json
import subprocess
import requests
import time
from pathlib import Path
from datetime import datetime
import argparse

class ProjectResume:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.services = {
            'whatsapp': {'port': 3002, 'path': 'services/whatsapp-service'},
            'classifier': {'port': 8001, 'path': 'services/classifier-service'},
            'ticket': {'port': 8005, 'path': 'services/ticket-service'},
            'redis': {'port': 6379, 'path': None}
        }
        
    def print_header(self, title):
        """Print formatted section header"""
        print(f"\n{'='*60}")
        print(f" {title}")
        print('='*60)
        
    def print_status(self, item, status, details=""):
        """Print formatted status line"""
        status_symbol = "[OK]" if status else "[FAIL]"
        print(f"{status_symbol} {item:<40} {details}")
        
    def read_file_safely(self, file_path):
        """Safely read file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
            
    def check_service_health(self, service_name, port):
        """Check if service is running and healthy"""
        try:
            if service_name == 'redis':
                # Simple TCP connection check for Redis
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                return result == 0
            else:
                # HTTP health check for other services
                health_endpoints = {
                    'whatsapp': f'http://localhost:{port}/api/health',
                    'classifier': f'http://localhost:{port}/health',
                    'ticket': f'http://localhost:{port}/health'
                }
                
                response = requests.get(health_endpoints[service_name], timeout=3)
                return response.status_code == 200
        except Exception:
            return False
            
    def get_git_status(self):
        """Get current git status"""
        try:
            # Get current branch
            branch = subprocess.check_output(['git', 'branch', '--show-current'], 
                                           cwd=self.project_root, text=True).strip()
            
            # Get status
            status = subprocess.check_output(['git', 'status', '--porcelain'], 
                                           cwd=self.project_root, text=True)
            
            # Get recent commits
            commits = subprocess.check_output(['git', 'log', '--oneline', '-5'], 
                                            cwd=self.project_root, text=True)
            
            return {
                'branch': branch,
                'status': status.strip(),
                'recent_commits': commits.strip().split('\n')
            }
        except Exception as e:
            return {'error': str(e)}
            
    def analyze_project_structure(self):
        """Analyze current project structure"""
        structure = {}
        
        # Check key files exist
        key_files = [
            'CLAUDE.md',
            'README.md', 
            'docker-compose.yml',
            'whatsapp-bot-specs.md',
            'services/whatsapp-service/package.json',
            'services/classifier-service/requirements.txt',
            'services/ticket-service/requirements.txt'
        ]
        
        for file_path in key_files:
            full_path = self.project_root / file_path
            structure[file_path] = {
                'exists': full_path.exists(),
                'size': full_path.stat().st_size if full_path.exists() else 0,
                'modified': datetime.fromtimestamp(full_path.stat().st_mtime).isoformat() if full_path.exists() else None
            }
            
        return structure
        
    def read_phase_status(self):
        """Read current phase and implementation status"""
        claude_md = self.project_root / 'CLAUDE.md'
        readme_md = self.project_root / 'README.md'
        
        status = {
            'phase': 'Unknown',
            'completed_features': [],
            'next_priorities': [],
            'known_issues': []
        }
        
        if claude_md.exists():
            content = self.read_file_safely(claude_md)
            
            # Extract phase information
            if 'Phase 1 Complete' in content:
                status['phase'] = 'Phase 1 Complete - Ready for Phase 2'
                
            # Extract completed features
            if '✅ Completed Components:' in content:
                lines = content.split('\n')
                in_completed = False
                for line in lines:
                    if '✅ Completed Components:' in line:
                        in_completed = True
                        continue
                    elif in_completed and line.startswith('- **'):
                        status['completed_features'].append(line.strip('- **').split('**')[0])
                    elif in_completed and not line.startswith('- '):
                        break
                        
        if readme_md.exists():
            content = self.read_file_safely(readme_md)
            
            # Extract next priorities
            if 'Phase 2 Roadmap' in content:
                lines = content.split('\n')
                in_roadmap = False
                for line in lines:
                    if 'Phase 2 Roadmap' in line:
                        in_roadmap = True
                        continue
                    elif in_roadmap and line.startswith('### Priority'):
                        status['next_priorities'].append(line.strip('### '))
                        
            # Extract known issues
            if 'Known Issues' in content:
                lines = content.split('\n')
                in_issues = False
                for line in lines:
                    if '### Known Issues' in line:
                        in_issues = True
                        continue
                    elif in_issues and line.startswith('- '):
                        status['known_issues'].append(line.strip('- '))
                    elif in_issues and line.startswith('#'):
                        break
                        
        return status
        
    def get_recent_activity(self):
        """Get recent development activity"""
        activity = {}
        
        # Check recent log files
        log_files = [
            'services/ticket-service/local_ticket.log',
            'services/whatsapp-service/whatsapp.log',
            'services/whatsapp-service/logs/whatsapp-service.log'
        ]
        
        for log_file in log_files:
            log_path = self.project_root / log_file
            if log_path.exists():
                try:
                    # Get last 5 lines
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        activity[log_file] = {
                            'last_modified': datetime.fromtimestamp(log_path.stat().st_mtime).isoformat(),
                            'recent_entries': [line.strip() for line in lines[-5:] if line.strip()]
                        }
                except Exception as e:
                    activity[log_file] = {'error': str(e)}
                    
        return activity
        
    def generate_resume_summary(self):
        """Generate comprehensive project resume summary"""
        
        # Project header
        self.print_header("WhatsApp Support Bot - Project Resume")
        print(f"[DATE] Resume Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[PATH] Project Root: {self.project_root}")
        
        # Phase status
        self.print_header("Current Implementation Status")
        phase_status = self.read_phase_status()
        print(f"[PHASE] Current Phase: {phase_status['phase']}")
        
        if phase_status['completed_features']:
            print("\n[DONE] Completed Features:")
            for feature in phase_status['completed_features'][:5]:  # Show top 5
                print(f"   * {feature}")
                
        if phase_status['next_priorities']:
            print("\n[NEXT] Next Priorities:")
            for priority in phase_status['next_priorities'][:3]:  # Show top 3
                print(f"   * {priority}")
                
        if phase_status['known_issues']:
            print("\n[WARN] Known Issues:")
            for issue in phase_status['known_issues']:
                print(f"   * {issue}")
                
        # Git status
        self.print_header("Git Repository Status")
        git_status = self.get_git_status()
        if 'error' not in git_status:
            print(f"[GIT] Current Branch: {git_status['branch']}")
            
            if git_status['status']:
                print("\n[CHANGES] Uncommitted Changes:")
                for line in git_status['status'].split('\n')[:10]:  # Show max 10
                    print(f"   {line}")
            else:
                print("[OK] Working directory clean")
                
            print("\n[COMMITS] Recent Commits:")
            for commit in git_status['recent_commits'][:3]:  # Show last 3
                print(f"   {commit}")
        else:
            print(f"[ERROR] Git Error: {git_status['error']}")
            
        # Service status
        self.print_header("Microservices Health Check")
        for service_name, config in self.services.items():
            is_healthy = self.check_service_health(service_name, config['port'])
            port_info = f":{config['port']}"
            self.print_status(f"{service_name.title()} Service", is_healthy, port_info)
            
        # Project structure
        self.print_header("Project Structure Analysis")
        structure = self.analyze_project_structure()
        
        for file_path, info in structure.items():
            if info['exists']:
                size_kb = info['size'] // 1024
                modified_date = info['modified'][:10] if info['modified'] else 'Unknown'
                details = f"{size_kb}KB - Modified: {modified_date}"
                self.print_status(file_path, True, details)
            else:
                self.print_status(file_path, False, "Missing")
                
        # Recent activity
        self.print_header("Recent Development Activity")
        activity = self.get_recent_activity()
        
        if activity:
            for log_file, info in activity.items():
                if 'error' not in info:
                    service_name = log_file.split('/')[1] if '/' in log_file else log_file
                    last_mod = info['last_modified'][:19].replace('T', ' ')
                    print(f"\n[LOG] {service_name} (Last: {last_mod}):")
                    for entry in info['recent_entries'][-3:]:  # Show last 3
                        # Truncate long lines
                        display_entry = entry[:80] + "..." if len(entry) > 80 else entry
                        print(f"   {display_entry}")
        else:
            print("No recent activity logs found")
            
        # Development recommendations
        self.print_header("Development Recommendations")
        
        # Check which services are down and suggest actions
        down_services = [name for name, config in self.services.items() 
                        if not self.check_service_health(name, config['port'])]
        
        if down_services:
            print("[ACTION] Services to Start:")
            for service in down_services:
                if service == 'redis':
                    print("   * Redis: docker-compose up redis -d")
                elif service == 'whatsapp':
                    print("   * WhatsApp: cd services/whatsapp-service && npm start")
                elif service == 'classifier':
                    print("   * Classifier: docker-compose up classifier-service -d")
                elif service == 'ticket':
                    print("   * Ticket: cd services/ticket-service && uv run uvicorn app.main:app --port 8005")
        else:
            print("[OK] All services are running")
            
        print("\n[READY] Ready to Continue with Phase 2:")
        print("   * Priority 1: Implement Conversation Service")
        print("   * Priority 2: Information Extractor with GPT-4 Vision")
        print("   * Priority 3: Vector Database (ChromaDB)")
        
        print("\n[COMMANDS] Useful Commands:")
        print("   * python resume_project.py --check-services  # Check service health")
        print("   * python resume_project.py --start-services  # Start stopped services")
        print("   * docker-compose up redis -d               # Start Redis")
        print("   * tail -f services/*/logs/*.log             # Monitor logs")
        
    def check_services_detailed(self):
        """Detailed service health check"""
        self.print_header("Detailed Service Health Check")
        
        for service_name, config in self.services.items():
            is_healthy = self.check_service_health(service_name, config['port'])
            
            if is_healthy:
                print(f"[OK] {service_name.title()} Service - Running on port {config['port']}")
                
                # Try to get additional info for HTTP services
                if service_name != 'redis':
                    try:
                        health_endpoints = {
                            'whatsapp': f'http://localhost:{config["port"]}/api/health',
                            'classifier': f'http://localhost:{config["port"]}/health',
                            'ticket': f'http://localhost:{config["port"]}/health'
                        }
                        
                        response = requests.get(health_endpoints[service_name], timeout=3)
                        if response.status_code == 200:
                            data = response.json()
                            if self.verbose:
                                print(f"   Status: {data.get('status', 'Unknown')}")
                                if 'uptime' in data:
                                    print(f"   Uptime: {data['uptime']}")
                                if 'version' in data:
                                    print(f"   Version: {data['version']}")
                    except Exception as e:
                        print(f"   Warning: Could not get detailed status - {e}")
            else:
                print(f"[FAIL] {service_name.title()} Service - Not running on port {config['port']}")
                
                # Suggest how to start
                if service_name == 'redis':
                    print("   Start with: docker-compose up redis -d")
                elif service_name == 'whatsapp':
                    print("   Start with: cd services/whatsapp-service && npm start")
                elif service_name == 'classifier':
                    print("   Start with: docker-compose up classifier-service -d")
                elif service_name == 'ticket':
                    print("   Start with: cd services/ticket-service && uv run uvicorn app.main:app --port 8005")
                    
    def start_services(self):
        """Attempt to start stopped services"""
        self.print_header("Starting Stopped Services")
        
        # Check Redis first
        if not self.check_service_health('redis', 6379):
            print("[START] Starting Redis...")
            try:
                subprocess.run(['docker-compose', 'up', 'redis', '-d'], 
                             cwd=self.project_root, check=True)
                time.sleep(3)  # Wait for Redis to start
                if self.check_service_health('redis', 6379):
                    print("[OK] Redis started successfully")
                else:
                    print("[FAIL] Redis failed to start")
            except Exception as e:
                print(f"[FAIL] Failed to start Redis: {e}")
        else:
            print("[OK] Redis already running")
            
        # Check Classifier service
        if not self.check_service_health('classifier', 8001):
            print("[START] Starting Classifier Service...")
            try:
                subprocess.run(['docker-compose', 'up', 'classifier-service', '-d'], 
                             cwd=self.project_root, check=True)
                time.sleep(5)  # Wait for service to start
                if self.check_service_health('classifier', 8001):
                    print("[OK] Classifier Service started successfully")
                else:
                    print("[FAIL] Classifier Service failed to start")
            except Exception as e:
                print(f"[FAIL] Failed to start Classifier Service: {e}")
        else:
            print("[OK] Classifier Service already running")
            
        # Note about manual services
        if not self.check_service_health('whatsapp', 3002):
            print("[MANUAL] WhatsApp Service needs manual start:")
            print("   cd services/whatsapp-service && npm start")
            
        if not self.check_service_health('ticket', 8005):
            print("[MANUAL] Ticket Service needs manual start:")
            print("   cd services/ticket-service && uv run uvicorn app.main:app --port 8005")

def main():
    parser = argparse.ArgumentParser(description='Resume WhatsApp Support Bot project development')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Show detailed information')
    parser.add_argument('--check-services', '-c', action='store_true',
                       help='Perform detailed service health check')
    parser.add_argument('--start-services', '-s', action='store_true',
                       help='Attempt to start stopped services')
    
    args = parser.parse_args()
    
    resume = ProjectResume(verbose=args.verbose)
    
    if args.check_services:
        resume.check_services_detailed()
    elif args.start_services:
        resume.start_services()
    else:
        resume.generate_resume_summary()
        
    print(f"\n{'='*60}")
    print(" Project Resume Complete - Ready to Continue Development")
    print('='*60)

if __name__ == '__main__':
    main()