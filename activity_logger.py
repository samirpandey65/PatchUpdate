import json
import os
from datetime import datetime

class ActivityLogger:
    def __init__(self, log_file='activity_log.json'):
        self.log_file = log_file
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Create log file if it doesn't exist"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                json.dump([], f)
    
    def log_activity(self, username, action, details=''):
        """Log user activity"""
        try:
            with open(self.log_file, 'r') as f:
                logs = json.load(f)
            
            logs.append({
                'timestamp': datetime.now().isoformat(),
                'username': username,
                'action': action,
                'details': details
            })
            
            # Keep only last 1000 logs
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            with open(self.log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error logging activity: {e}")
            return False
    
    def get_logs(self, username=None, limit=100):
        """Get activity logs"""
        try:
            with open(self.log_file, 'r') as f:
                logs = json.load(f)
            
            if username:
                logs = [log for log in logs if log['username'] == username]
            
            return logs[-limit:][::-1]  # Return last N logs, newest first
        except Exception as e:
            print(f"Error reading logs: {e}")
            return []
