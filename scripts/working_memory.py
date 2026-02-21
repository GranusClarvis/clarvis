#!/usr/bin/env python3
"""
Working Memory Buffer — GWT-inspired conscious attention spotlight

This implements the Global Workspace Theory's "spotlight" — a short-term 
buffer that holds the current focus of attention and broadcasts it to all 
cognitive components.
"""

import json
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

WORKING_MEM_FILE = Path("/home/agent/.openclaw/workspace/data/working_memory_state.json")

# Configuration
MAX_ITEMS = 10  # Maximum items in working memory
ITEM_TTL_SECONDS = 300  # 5 minutes default TTL
PERSIST_TTL_SECONDS = 3600  # 1 hour — extended TTL for items restored from disk

class WorkingMemoryBuffer:
    """GWT-inspired working memory with attention spotlight."""
    
    def __init__(self, max_items=MAX_ITEMS, ttl=ITEM_TTL_SECONDS):
        self.max_items = max_items
        self.ttl = ttl
        self.load_from_disk()

    def _reset(self):
        """Reset to empty state."""
        self.items = deque()
        self.spotlight = None
        self.last_update = datetime.now()

    def _save(self):
        """Persist to disk (internal — called after every mutation)."""
        self.save_to_disk()

    def save_to_disk(self):
        """
        Serialize the full working memory state to data/working_memory_state.json.
        Called after every heartbeat and every mutation.
        """
        WORKING_MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "items": list(self.items),
            "spotlight": self.spotlight,
            "last_update": self.last_update.isoformat(),
            "saved_at": datetime.now().isoformat()
        }
        WORKING_MEM_FILE.write_text(json.dumps(data, indent=2))

    def load_from_disk(self):
        """
        Load working memory state from data/working_memory_state.json.
        Extends TTLs of restored items so working memory survives restarts.
        Called on boot (init).
        """
        if WORKING_MEM_FILE.exists():
            try:
                data = json.loads(WORKING_MEM_FILE.read_text())
                raw_items = data.get("items", [])
                now = datetime.now()

                # Extend TTLs for items that would otherwise expire after restart
                restored_items = []
                for item in raw_items:
                    expires = datetime.fromisoformat(item["expires"])
                    if expires < now:
                        # Item expired — extend with persist TTL to keep it alive
                        item["expires"] = (now + timedelta(seconds=PERSIST_TTL_SECONDS)).isoformat()
                    restored_items.append(item)

                self.items = deque(restored_items)
                self.spotlight = data.get("spotlight", None)
                self.last_update = datetime.fromisoformat(
                    data.get("last_update", now.isoformat())
                )
            except Exception:
                self._reset()
        else:
            self._reset()
    
    def add(self, content: str, importance: float = 0.5, source: str = "system"):
        """
        Add item to working memory. If it's high importance, make it the spotlight.
        """
        item = {
            "content": content,
            "importance": importance,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "expires": (datetime.now() + timedelta(seconds=self.ttl)).isoformat()
        }
        
        # Add to front (most recent)
        self.items.appendleft(item)
        
        # Maintain max size
        while len(self.items) > self.max_items:
            self.items.pop()
        
        # Auto-spotlight high importance items
        if importance >= 0.8:
            self.spotlight = content
        
        self.last_update = datetime.now()
        self._save()
        return item
    
    def spotlight_on(self, content: str):
        """Manually set the spotlight (attention focus)."""
        self.spotlight = content
        self.last_update = datetime.now()
        self._save()
    
    def get_spotlight(self):
        """Get current attention focus."""
        # Check if spotlight expired
        if self.spotlight:
            # Check if it's still in items and not expired
            for item in self.items:
                if item["content"] == self.spotlight:
                    exp = datetime.fromisoformat(item["expires"])
                    if datetime.now() < exp:
                        return self.spotlight
            # Spotlight expired, clear it
            self.spotlight = None
            self._save()
        return self.spotlight
    
    def get_all(self):
        """Get all valid items (not expired)."""
        now = datetime.now()
        valid = []
        for item in self.items:
            exp = datetime.fromisoformat(item["expires"])
            if now < exp:
                valid.append(item)
        return valid
    
    def broadcast(self) -> dict:
        """
        Get everything that should be broadcast to all cognitive components.
        This is the "global workspace" output.
        """
        return {
            "spotlight": self.get_spotlight(),
            "recent": self.get_all()[:5],  # Top 5 recent items
            "timestamp": datetime.now().isoformat()
        }
    
    def clear_expired(self):
        """Remove expired items."""
        now = datetime.now()
        new_items = deque()
        for item in self.items:
            exp = datetime.fromisoformat(item["expires"])
            if now < exp:
                new_items.append(item)
        self.items = new_items
        
        # Clear spotlight if it's not in valid items
        if self.spotlight:
            valid_contents = [i["content"] for i in self.items]
            if self.spotlight not in valid_contents:
                self.spotlight = None
        
        self._save()
    
    def __len__(self):
        return len(self.items)
    
    def __repr__(self):
        return f"WorkingMemoryBuffer(items={len(self)}, spotlight={self.get_spotlight()[:50] if self.get_spotlight() else None})"


# Global instance
_wm_buffer = None

def get_buffer() -> WorkingMemoryBuffer:
    """Get or create the global working memory buffer."""
    global _wm_buffer
    if _wm_buffer is None:
        _wm_buffer = WorkingMemoryBuffer()
        # Clean expired on load
        _wm_buffer.clear_expired()
    return _wm_buffer


# CLI interface
if __name__ == "__main__":
    import sys
    
    wm = get_buffer()
    
    if len(sys.argv) < 2:
        print("Working Memory Buffer (GWT-inspired)")
        print(f"Current: {wm}")
        print("\nBroadcast (what all components see):")
        print(json.dumps(wm.broadcast(), indent=2))
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "add":
        content = sys.argv[2] if len(sys.argv) > 2 else input("Content: ")
        importance = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        wm.add(content, importance)
        print(f"Added to working memory (importance={importance})")
    
    elif cmd == "spotlight":
        content = sys.argv[2] if len(sys.argv) > 2 else input("Content: ")
        wm.spotlight_on(content)
        print(f"Spotlight set to: {content}")
    
    elif cmd == "spotlight-get":
        print(f"Current spotlight: {wm.get_spotlight()}")
    
    elif cmd == "broadcast":
        print(json.dumps(wm.broadcast(), indent=2))
    
    elif cmd == "clear":
        wm._reset()
        wm._save()
        print("Working memory cleared")
    
    elif cmd == "clean":
        wm.clear_expired()
        print(f"Cleaned. Current: {wm}")

    elif cmd == "save":
        wm.save_to_disk()
        print(f"Saved to {WORKING_MEM_FILE}")

    elif cmd == "load":
        wm.load_from_disk()
        print(f"Loaded from {WORKING_MEM_FILE}: {wm}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: add, spotlight, spotlight-get, broadcast, clear, clean, save, load")