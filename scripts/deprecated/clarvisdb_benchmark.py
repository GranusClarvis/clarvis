#!/usr/bin/env python3
"""
ClarvisDB Comprehensive Benchmark
Tests the actual ClarvisDB memory system
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, "/home/agent/.openclaw/workspace/scripts")

def test_database_exists():
    """Test 1: Database files exist"""
    print("=" * 60)
    print("TEST 1: Database Files")
    print("=" * 60)
    
    db_path = "/home/agent/.openclaw/workspace/data/clarvisdb"
    required = ["chroma.sqlite3", "relationships.json"]
    
    for f in required:
        full_path = os.path.join(db_path, f)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print(f"✓ {f}: {size} bytes")
        else:
            print(f"✗ {f}: MISSING")
            return False
    return True


def test_chromadb_import():
    """Test 2: ChromaDB import and connection"""
    print("\n" + "=" * 60)
    print("TEST 2: ChromaDB Connection")
    print("=" * 60)
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path="/home/agent/.openclaw/workspace/data/clarvisdb")
        
        # Check collections
        collections = client.list_collections()
        print(f"✓ ChromaDB connected")
        print(f"  Collections: {[c.name for c in collections]}")
        return True
    except Exception as e:
        print(f"✗ ChromaDB failed: {e}")
        return False


def test_collections():
    """Test 3: Required collections exist"""
    print("\n" + "=" * 60)
    print("TEST 3: Collections")
    print("=" * 60)
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path="/home/agent/.openclaw/workspace/data/clarvisdb")
        
        required = ["clarvis-identity", "clarvis-preferences", "clarvis-learnings", "clarvis-infrastructure"]
        all_exist = True
        
        for name in required:
            try:
                col = client.get_collection(name)
                count = col.count()
                print(f"✓ {name}: {count} memories")
            except:
                print(f"✗ {name}: MISSING")
                all_exist = False
        
        return all_exist
    except Exception as e:
        print(f"✗ Collections check failed: {e}")
        return False


def test_graph_layer():
    """Test 4: Graph relationships"""
    print("\n" + "=" * 60)
    print("TEST 4: Graph Layer")
    print("=" * 60)
    
    try:
        graph_path = "/home/agent/.openclaw/workspace/data/clarvisdb/relationships.json"
        with open(graph_path) as f:
            graph = json.load(f)
        
        nodes = len(graph.get("nodes", {}))
        edges = len(graph.get("edges", []))
        print(f"✓ Graph: {nodes} nodes, {edges} edges")
        
        if nodes > 0 and edges > 0:
            return True
        else:
            print("✗ Graph is empty")
            return False
    except Exception as e:
        print(f"✗ Graph check failed: {e}")
        return False


def test_store_recall():
    """Test 5: Store and recall"""
    print("\n" + "=" * 60)
    print("TEST 5: Store & Recall")
    print("=" * 60)
    
    try:
        from clarvisdb import add_memory, query_memory, LEARNINGS
        
        # Store test memory
        test_id = f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        add_memory(LEARNINGS, "BENCHMARK TEST MEMORY", {"importance": 0.9, "source": "benchmark", "tags": ["test"]}, memory_id=test_id)
        print(f"✓ Stored test memory: {test_id}")
        
        # Recall it
        results = query_memory(LEARNINGS, "BENCHMARK TEST", n=5)
        found = any("BENCHMARK" in doc for doc in results.get("documents", [[]])[0])
        
        if found:
            print(f"✓ Recall works - found stored memory")
            return True
        else:
            print(f"✗ Recall failed to find stored memory")
            return False
    except Exception as e:
        print(f"✗ Store/recall failed: {e}")
        return False


def test_integration_layer():
    """Test 6: Integration layer"""
    print("\n" + "=" * 60)
    print("TEST 6: Integration Layer")
    print("=" * 60)
    
    try:
        from clarvisdb_integrate import store_important, recall
        
        # Store via integration
        store_important("INTEGRATION TEST", "clarvis-learnings", 0.8, "benchmark")
        print("✓ store_important works")
        
        # Recall via integration
        results = recall("INTEGRATION")
        if results:
            print(f"✓ recall works: {len(results)} results")
            return True
        else:
            print("✗ recall returned nothing")
            return False
    except Exception as e:
        print(f"✗ Integration failed: {e}")
        return False


def test_cli():
    """Test 7: CLI tool"""
    print("\n" + "=" * 60)
    print("TEST 7: CLI Tool")
    print("=" * 60)
    
    cli_path = "/home/agent/.openclaw/workspace/scripts/clarvisdb_cli.py"
    if not os.path.exists(cli_path):
        print(f"✗ CLI not found: {cli_path}")
        return False
    
    print(f"✓ CLI exists")
    
    # Test recall via CLI
    import subprocess
    result = subprocess.run(
        ["python3", cli_path, "recall", "who am I"],
        capture_output=True, text=True, cwd="/home/agent/.openclaw/workspace"
    )
    
    if result.returncode == 0 and "My creator" in result.stdout:
        print(f"✓ CLI recall works")
        return True
    else:
        print(f"✗ CLI recall failed: {result.stderr}")
        return False


def test_skill():
    """Test 8: Skill documentation"""
    print("\n" + "=" * 60)
    print("TEST 8: Skill Documentation")
    print("=" * 60)
    
    skill_path = "/home/agent/.openclaw/skills/clarvisdb/SKILL.md"
    if not os.path.exists(skill_path):
        print(f"✗ Skill not found: {skill_path}")
        return False
    
    with open(skill_path) as f:
        content = f.read()
    
    # Check for key sections
    checks = ["store", "recall", "collection", "integration"]
    found = sum(1 for c in checks if c.lower() in content.lower())
    
    print(f"✓ Skill exists: {found}/{len(checks)} key sections")
    return found >= 3


def test_agents_auto_load():
    """Test 9: AGENTS.md auto-load"""
    print("\n" + "=" * 60)
    print("TEST 9: AGENTS.md Auto-Load")
    print("=" * 60)
    
    agents_path = "/home/agent/.openclaw/workspace/AGENTS.md"
    with open(agents_path) as f:
        content = f.read()
    
    if "clarvisdb" in content.lower() or "clarvisdb_integrate" in content:
        print(f"✓ Auto-load configured in AGENTS.md")
        return True
    else:
        print(f"✗ Auto-load NOT configured")
        return False


def run_all():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("CLARVISDB COMPREHENSIVE BENCHMARK")
    print("=" * 60 + "\n")
    
    results = {
        "database_exists": test_database_exists(),
        "chromadb_connection": test_chromadb_import(),
        "collections": test_collections(),
        "graph_layer": test_graph_layer(),
        "store_recall": test_store_recall(),
        "integration_layer": test_integration_layer(),
        "cli_tool": test_cli(),
        "skill_doc": test_skill(),
        "auto_load": test_agents_auto_load()
    }
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:25} {status}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    from datetime import timezone
    success = run_all()
    sys.exit(0 if success else 1)
