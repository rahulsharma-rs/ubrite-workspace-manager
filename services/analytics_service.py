import json
import os
from datetime import datetime
from flask import current_app

class AnalyticsService:
    def __init__(self):
        self._enabled = None
        self._analytics_file = None
    
    @property
    def enabled(self):
        if self._enabled is None:
            self._enabled = current_app.config['ANALYTICS_ENABLED']
        return self._enabled
    
    @property
    def analytics_file(self):
        if self._analytics_file is None:
            self._analytics_file = os.path.join(
                current_app.config['UBRITE_ROOT'],
                '.analytics.json'
            )
        return self._analytics_file
    
    def track_event(self, event_name, payload):
        """Track an analytics event."""
        if not self.enabled:
            return
        
        event = {
            'event': event_name,
            'timestamp': datetime.utcnow().isoformat(),
            'payload': payload
        }
        
        self._append_event(event)
    
    def _append_event(self, event):
        """Append an event to the analytics file."""
        events = []
        
        if os.path.exists(self.analytics_file):
            try:
                with open(self.analytics_file, 'r') as f:
                    events = json.load(f)
            except json.JSONDecodeError:
                events = []
        
        events.append(event)
        
        with open(self.analytics_file, 'w') as f:
            json.dump(events, f, indent=2)
    
    def get_events(self, event_type=None, limit=100):
        """Get analytics events."""
        if not os.path.exists(self.analytics_file):
            return []
        
        try:
            with open(self.analytics_file, 'r') as f:
                events = json.load(f)
            
            if event_type:
                events = [e for e in events if e['event'] == event_type]
            
            return events[-limit:]
        except json.JSONDecodeError:
            return []
