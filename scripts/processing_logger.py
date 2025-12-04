"""
Processing Logger for real-time UI feedback
Handles logging of OCR and dictionary indexing progress
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from threading import Lock


class ProcessingLogger:
    """Thread-safe logger for tracking processing progress"""
    
    def __init__(self):
        self.logs = {}  # Store logs by session/upload ID
        self.lock = Lock()
    
    def create_session(self, session_id: str, filename: str, total_pages: int = 1) -> None:
        """Create a new processing session"""
        with self.lock:
            self.logs[session_id] = {
                'filename': filename,
                'total_pages': total_pages,
                'current_page': 0,
                'status': 'started',
                'started_at': datetime.utcnow().isoformat(),
                'logs': [],
                'stats': {
                    'pages_processed': 0,
                    'words_indexed': 0,
                    'entries_created': 0,
                    'ocr_method': None,
                    'errors': 0
                }
            }
    
    def log(self, session_id: str, message: str, level: str = 'info', data: Optional[Dict] = None) -> None:
        """Add a log entry"""
        with self.lock:
            if session_id not in self.logs:
                return
            
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'level': level,
                'message': message,
                'data': data or {}
            }
            
            self.logs[session_id]['logs'].append(log_entry)
            
            # Keep only last 100 log entries per session
            if len(self.logs[session_id]['logs']) > 100:
                self.logs[session_id]['logs'] = self.logs[session_id]['logs'][-100:]
    
    def update_page(self, session_id: str, page_number: int) -> None:
        """Update current page being processed"""
        with self.lock:
            if session_id in self.logs:
                self.logs[session_id]['current_page'] = page_number
                self.logs[session_id]['stats']['pages_processed'] = page_number
    
    def update_stats(self, session_id: str, **kwargs) -> None:
        """Update processing statistics"""
        with self.lock:
            if session_id in self.logs:
                self.logs[session_id]['stats'].update(kwargs)
    
    def set_status(self, session_id: str, status: str) -> None:
        """Set processing status"""
        with self.lock:
            if session_id in self.logs:
                self.logs[session_id]['status'] = status
                if status in ['completed', 'failed']:
                    self.logs[session_id]['completed_at'] = datetime.utcnow().isoformat()
    
    def get_logs(self, session_id: str) -> Optional[Dict]:
        """Get logs for a session"""
        with self.lock:
            return self.logs.get(session_id, {}).copy() if session_id in self.logs else None
    
    def get_recent_logs(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get recent log entries"""
        with self.lock:
            if session_id not in self.logs:
                return []
            return self.logs[session_id]['logs'][-limit:]
    
    def cleanup_old_sessions(self, max_age_minutes: int = 60) -> None:
        """Clean up old completed sessions"""
        with self.lock:
            current_time = datetime.utcnow()
            to_remove = []
            
            for session_id, session_data in self.logs.items():
                if session_data.get('status') in ['completed', 'failed']:
                    if 'completed_at' in session_data:
                        completed_time = datetime.fromisoformat(session_data['completed_at'])
                        age_minutes = (current_time - completed_time).total_seconds() / 60
                        if age_minutes > max_age_minutes:
                            to_remove.append(session_id)
            
            for session_id in to_remove:
                del self.logs[session_id]


# Global logger instance
processing_logger = ProcessingLogger()