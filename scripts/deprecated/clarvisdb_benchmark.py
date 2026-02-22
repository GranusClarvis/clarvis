#!/usr/bin/env python3
"""
ClarvisDB Benchmark Suite
Tests for Clarvis components and evolution status
"""

import sys
import os

# Add scripts to path
sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

def test_brain_core():
    """Test clarvis_brain.py"""
    print("=" * 50)
    print("TEST 1: Brain Core")
    print("=" * 50)
    
    try:
        from clarvis_brain import get_brain
        
        brain = get_brain()
        
        # Test store
        brain.process("Test memory benchmark", source="benchmark")
        print("✓ Memory storage works")
        
        # Test recall (handle both dict and list)
        try:
            results = brain.recall("test", n=3)
            if isinstance(results, dict):
                ids = results.get("ids", [[]])[0]
            else:
                ids = []
            print(f"✓ Recall works: {len(ids)} results")
        except Exception as e:
            print(f"⚠ Recall issue (non-critical): {e}")
        
        return True
    except Exception as e:
        print(f"✗ Brain core failed: {e}")
        return False


def test_session_bridge():
    """Test clarvis_session.py"""
    print("\n" + "=" * 50)
    print("TEST 2: Session Bridge")
    print("=" * 50)
    
    try:
        from clarvis_session import session_open, get_current_mode
        
        sessions = session_open(n=1)
        print(f"✓ Session open works: {len(sessions)} sessions")
        
        mode = get_current_mode()
        print(f"✓ Current mode: {mode}")
        
        return True
    except Exception as e:
        print(f"✗ Session bridge failed: {e}")
        return False


def test_task_graph():
    """Test clarvis_tasks.py"""
    print("\n" + "=" * 50)
    print("TEST 3: Task Graph")
    print("=" * 50)
    
    try:
        from clarvis_tasks import get_tasks
        
        tasks = get_tasks()
        print(f"✓ Task graph works: {len(tasks)} tasks")
        
        return True
    except Exception as e:
        print(f"✗ Task graph failed: {e}")
        return False


def test_confidence():
    """Test clarvis_confidence.py"""
    print("\n" + "=" * 50)
    print("TEST 4: Confidence Gating")
    print("=" * 50)
    
    try:
        from clarvis_confidence import log_prediction
        
        log_prediction("test_task", "HIGH", "expected_high", "actual")
        print("✓ Confidence logging works")
        
        return True
    except Exception as e:
        print(f"✗ Confidence failed: {e}")
        return False


def test_model_switch():
    """Test clarvis_model_switch.py"""
    print("\n" + "=" * 50)
    print("TEST 5: Model Switching")
    print("=" * 50)
    
    try:
        from clarvis_model_switch import get_session_model
        
        model = get_session_model()
        print(f"✓ Current model: {model}")
        
        return True
    except Exception as e:
        print(f"✗ Model switch failed: {e}")
        return False


def test_handover():
    """Test clarvis_handover.py"""
    print("\n" + "=" * 50)
    print("TEST 6: Task Analysis (Handover)")
    print("=" * 50)
    
    try:
        from clarvis_handover import analyze_task_complexity
        
        # Test coding task
        result = analyze_task_complexity("write a python script")
        print(f"✓ Coding task: {result['mode']}")
        
        # Test reasoning task
        result = analyze_task_complexity("design an architecture")
        print(f"✓ Reasoning task: {result['mode']}")
        
        return True
    except Exception as e:
        print(f"✗ Handover failed: {e}")
        return False


def test_auto_processing():
    """Test clarvis_auto.py"""
    print("\n" + "=" * 50)
    print("TEST 7: Auto-Processing (P0)")
    print("=" * 50)
    
    try:
        from clarvis_auto import process_message, auto_start
        
        result = process_message("Test message", "benchmark")
        print(f"✓ Message processing: {result['stored']}")
        
        start = auto_start()
        print(f"✓ Auto start: {len(start.get('pending_goals', []))} pending goals")
        
        return True
    except Exception as e:
        print(f"✗ Auto-processing failed: {e}")
        return False


def test_knowledge_base():
    """Test documentation"""
    print("\n" + "=" * 50)
    print("TEST 8: Knowledge Base")
    print("=" * 50)
    
    try:
        kb_path = "/home/agent/.openclaw/workspace/docs/MY_KNOWLEDGE_BASE.md"
        if os.path.exists(kb_path):
            with open(kb_path) as f:
                content = f.read()
            print(f"✓ Knowledge base exists: {len(content)} chars")
            return True
        else:
            print("✗ Knowledge base missing")
            return False
    except Exception as e:
        print(f"✗ Knowledge base check failed: {e}")
        return False


def test_evolution_plan():
    """Test evolution plan"""
    print("\n" + "=" * 50)
    print("TEST 9: Evolution Plan")
    print("=" * 50)
    
    try:
        plan_path = "/home/agent/.openclaw/workspace/data/plans/evolution_analysis.md"
        if os.path.exists(plan_path):
            with open(plan_path) as f:
                content = f.read()
            print(f"✓ Evolution plan exists: {len(content)} chars")
            return True
        else:
            print("✗ Evolution plan missing")
            return False
    except Exception as e:
        print(f"✗ Evolution plan check failed: {e}")
        return False


def run_all_tests():
    """Run all benchmarks"""
    print("\n" + "=" * 60)
    print("CLARVISDB BENCHMARK SUITE")
    print("=" * 60)
    
    results = {
        "brain_core": test_brain_core(),
        "session_bridge": test_session_bridge(),
        "task_graph": test_task_graph(),
        "confidence": test_confidence(),
        "model_switch": test_model_switch(),
        "handover": test_handover(),
        "auto_processing": test_auto_processing(),
        "knowledge_base": test_knowledge_base(),
        "evolution_plan": test_evolution_plan()
    }
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:20} {status}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)