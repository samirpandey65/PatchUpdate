import hashlib
import json
import os
from datetime import datetime, timedelta

class UserAuth:
    def __init__(self, users_file='users.json'):
        self.users_file = users_file
        self._ensure_users_file()
    
    def _ensure_users_file(self):
        """Create users file if it doesn't exist with default admin user"""
        if not os.path.exists(self.users_file):
            default_users = {
                'admin': {
                    'password': self._hash_password('admin123'),
                    'role': 'admin',
                    'created': datetime.now().isoformat()
                }
            }
            with open(self.users_file, 'w') as f:
                json.dump(default_users, f, indent=2)
    
    def _hash_password(self, password):
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self, username, password):
        """Authenticate user credentials"""
        try:
            with open(self.users_file, 'r') as f:
                users = json.load(f)
            
            if username in users:
                hashed_password = self._hash_password(password)
                if users[username]['password'] == hashed_password:
                    return {
                        'success': True,
                        'username': username,
                        'role': users[username].get('role', 'user')
                    }
            
            return {'success': False, 'error': 'Invalid username or password'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_user(self, username, password, role='user'):
        """Add new user"""
        try:
            with open(self.users_file, 'r') as f:
                users = json.load(f)
            
            if username in users:
                return {'success': False, 'error': 'User already exists'}
            
            users[username] = {
                'password': self._hash_password(password),
                'role': role,
                'created': datetime.now().isoformat()
            }
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def change_password(self, username, old_password, new_password):
        """Change user password"""
        try:
            with open(self.users_file, 'r') as f:
                users = json.load(f)
            
            if username not in users:
                return {'success': False, 'error': 'User not found'}
            
            if users[username]['password'] != self._hash_password(old_password):
                return {'success': False, 'error': 'Invalid old password'}
            
            users[username]['password'] = self._hash_password(new_password)
            users[username]['updated'] = datetime.now().isoformat()
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def edit_user(self, username, password=None, role=None):
        """Edit user details"""
        try:
            with open(self.users_file, 'r') as f:
                users = json.load(f)
            
            if username not in users:
                return {'success': False, 'error': 'User not found'}
            
            if password:
                users[username]['password'] = self._hash_password(password)
            
            if role:
                users[username]['role'] = role
            
            users[username]['updated'] = datetime.now().isoformat()
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def delete_user(self, username):
        """Delete user"""
        try:
            with open(self.users_file, 'r') as f:
                users = json.load(f)
            
            if username not in users:
                return {'success': False, 'error': 'User not found'}
            
            if username == 'admin':
                return {'success': False, 'error': 'Cannot delete admin user'}
            
            del users[username]
            
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_users(self):
        """List all users"""
        try:
            with open(self.users_file, 'r') as f:
                users = json.load(f)
            
            user_list = []
            for username, data in users.items():
                user_list.append({
                    'username': username,
                    'role': data.get('role', 'user'),
                    'created': data.get('created', 'N/A')
                })
            
            return {'success': True, 'users': user_list}
        except Exception as e:
            return {'success': False, 'error': str(e)}
