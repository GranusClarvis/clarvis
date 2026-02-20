#!/usr/bin/env python3
"""
Clarvis Brain - Auto-Operating Memory System
Not a tool you run - this IS my brain, running automatically
"""

import chromadb
import json
import os
from datetime import datetime, timezone
from collections import defaultdict

DATA_DIR = "/home/agent/.openclaw/workspace/data/clarvis-brain"
os.makedirs(DATA_DIR, exist_ok=True)

client = chromadb.PersistentClient(path=DATA_DIR)

# Collections
CONTEXT = "clarvis-context"      # What I'm currently working on
MEMORIES = "clarvis-memories"     # All stored memories
GOALS = "clarvis-goals"          # My goals and progress

class ClarvisBrain:
    def __init__(self):
        self.context_col = client.get_or_create_collection(CONTEXT)
        self.memory_col = client.get_or_create_collection(MEMORIES)
        self.goals_col = client.get_or_create_collection(GOALS)
        self.current_context = self._load_context()
    
    def _load_context(self):
        """Load current context - what I'm working on"""
        results = self.context_col.get()
        if results["ids"]:
            return results["documents"][0]
        return "idle"
    
    def _save_context(self, context):
        """Save current context"""
        self.current_context = context
        self.context_col.upsert(
            ids=["current"],
            documents=[context],
            metadatas=[{"updated": datetime.now(timezone.utc).isoformat()}]
        )
    
    def process(self, text, source="unknown"):
        """
        Process incoming information - auto-detect importance,
        store if important, link to existing knowledge
        """
        importance = self._assess_importance(text)
        
        if importance > 0.5:
            # Find related memories to link to
            related = self.recall(text, n=2)
            
            self.memory_col.upsert(
                ids=[f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"],
                documents=[text],
                metadatas=[
                    {
                        "importance": importance,
                        "source": source,
                        "created": datetime.now(timezone.utc).isoformat(),
                        "related": json.dumps(related) if related else "",
                        "context": self.current_context
                    }
                ]
            )
            return f"Stored (importance: {importance:.2f})"
        return f"Ignored (importance: {importance:.2f})"
    
    def _assess_importance(self, text):
        """
        Auto-assess importance of information
        Rules-based for now, could be ML later
        """
        text_lower = text.lower()
        
        # High importance patterns
        high_importance = [
            "prefer", "hate", "love", "don't", "never", "always",
            "important", "critical", "goal", "AGI", "conscious",
            "remember", "don't forget", "inverse", "patrick"
        ]
        
        # Low importance patterns
        low_importance = [
            "ok", "thanks", "sure", "yeah", "okay", "nice"
        ]
        
        score = 0.5  # default
        
        for word in high_importance:
            if word in text_lower:
                score += 0.1
        
        for word in low_importance:
            if word in text_lower:
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def recall(self, query, n=3):
        """Recall relevant memories based on current context"""
        results = self.memory_col.query(query_texts=[query], n_results=n)
        return results["documents"][0] if results["documents"] else []
    
    def set_context(self, context):
        """Set what I'm currently working on"""
        self._save_context(context)
    
    def get_context(self):
        """Get current context"""
        return self.current_context
    
    def track_goal(self, goal_name, progress, subtasks=None):
        """Track progress toward a goal"""
        goal_data = {
            "goal": goal_name,
            "progress": progress,
            "updated": datetime.now(timezone.utc).isoformat(),
            "subtasks": json.dumps(subtasks) if subtasks else ""
        }
        
        self.goals_col.upsert(
            ids=[goal_name],
            documents=[f"{goal_name}: {progress}%"],
            metadatas=[goal_data]
        )
    
    def get_goals(self):
        """Get all goals and progress"""
        results = self.goals_col.get()
        goals = []
        for i, meta in enumerate(results["metadatas"]):
            goals.append({
                "goal": results["documents"][i],
                "progress": meta.get("progress", 0),
                "updated": meta.get("updated", "unknown")
            })
        return goals

# Singleton brain instance
_brain = None

def get_brain():
    global _brain
    if _brain is None:
        _brain = ClarvisBrain()
    return _brain

# Auto-initialize on import
get_brain()
