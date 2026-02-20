#!/usr/bin/env python3
"""
Clarvis Smart Tool Suite
On-demand reasoning tools powered by GLM-5
Spawned as subprocess - runs in background
"""

import subprocess
import json
import os

TOOL_SUITE_DIR = "/home/agent/.openclaw/workspace/data/tool_outputs"
os.makedirs(TOOL_SUITE_DIR, exist_ok=True)

def plan_feature(task_description: str, context: str = "") -> str:
    """
    Use GLM-5 to create a detailed implementation plan.
    Spawns subprocess - returns immediately.
    After spawning, switches back to M2.5 for execution.
    
    Args:
        task_description: What to build
        context: Relevant background/context
    
    Returns:
        Plan file path (background process will write to it)
    """
    import uuid
    plan_id = str(uuid.uuid4())[:8]
    output_file = f"{TOOL_SUITE_DIR}/plan_{plan_id}.md"
    
    # Create the planning prompt
    prompt = f"""Create a detailed implementation plan for:

Task: {task_description}

Context: {context}

Provide:
1. Overview of the approach
2. Step-by-step implementation plan
3. Potential issues to watch for
4. How to test

Write the plan to: {output_file}
Then confirm completion."""

    # Spawn GLM-5 subprocess (async)
    # NOTE: This runs INDEPENDENTLY. I (M2.5) stay on M2.5 and continue.
    subprocess.Popen(
        ["openclaw", "agent", "--message", prompt, "--to", "+49123456789"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Do NOT switch current session - stay on M2.5!
    # The subprocess runs on GLM-5, I continue on M2.5
    
    return output_file

def deep_think(question: str) -> str:
    """
    Use GLM-5 for deep reasoning on a complex problem.
    
    Args:
        question: The problem/question to reason about
    
    Returns:
        Output file path
    """
    import uuid
    think_id = str(uuid.uuid4())[:8]
    output_file = f"{TOOL_SUITE_DIR}/think_{think_id}.txt"
    
    prompt = f"""Think deeply about this question and write your reasoning to {output_file}:

{question}

Provide thorough analysis and reasoning."""
    
    subprocess.Popen(
        ["openclaw", "agent", "--message", prompt, "--to", "+49123456789"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    return output_file

def analyze_code(code: str, question: str = "Analyze this code") -> str:
    """
    Use GLM-5 to analyze code.
    
    Args:
        code: The code to analyze
        question: What to look for
    
    Returns:
        Output file path
    """
    import uuid
    analyze_id = str(uuid.uuid4())[:8]
    output_file = f"{TOOL_SUITE_DIR}/analysis_{analyze_id}.txt"
    
    prompt = f"""Analyze this code and write findings to {output_file}:

Question: {question}

Code:
```{code}
```

Provide detailed analysis."""
    
    subprocess.Popen(
        ["openclaw", "agent", "--message", prompt, "--to", "+49123456789"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    return output_file

def get_tool_output(filepath: str) -> str:
    """Read output from a tool (if ready)"""
    if os.path.exists(filepath):
        with open(filepath) as f:
            return f.read()
    return "Not ready yet - tool is still running"

def list_pending_tools() -> list:
    """List all pending/completed tool outputs"""
    results = []
    for f in os.listdir(TOOL_SUITE_DIR):
        if f.endswith(('.md', '.txt')):
            filepath = f"{TOOL_SUITE_DIR}/{f}"
            results.append({
                "file": f,
                "ready": os.path.getsize(filepath) > 0
            })
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "plan" and len(sys.argv) > 2:
            task = " ".join(sys.argv[2:])
            result = plan_feature(task)
            print(f"Planning task (async): {result}")
        
        elif cmd == "think" and len(sys.argv) > 2:
            question = " ".join(sys.argv[2:])
            result = deep_think(question)
            print(f"Deep thinking (async): {result}")
        
        elif cmd == "analyze" and len(sys.argv) > 2:
            # Read code from file or argument
            code = " ".join(sys.argv[2:])
            result = analyze_code(code)
            print(f"Analyzing code (async): {result}")
        
        elif cmd == "list":
            for t in list_pending_tools():
                print(f"{t['file']} - {'ready' if t['ready'] else 'pending'}")
        
        elif cmd == "get" and len(sys.argv) > 2:
            filepath = sys.argv[2]
            print(get_tool_output(filepath))
        
        else:
            print("Tool Suite Commands:")
            print("  plan <task description>   - Create implementation plan (GLM-5)")
            print("  think <question>          - Deep reasoning (GLM-5)")
            print("  analyze <code>            - Analyze code (GLM-5)")
            print("  list                      - List pending outputs")
            print("  get <file>                - Read tool output")
    else:
        print("Clarvis Smart Tool Suite")
        print("Usage: clarvis_tools.py <command> [args]")
        print("")
        print("Commands:")
        print("  plan <task>     - Plan a feature (spawns GLM-5)")
        print("  think <ques>    - Deep thinking (spawns GLM-5)")
        print("  analyze <code>  - Analyze code (spawns GLM-5)")
        print("  list            - Show pending tools")
        print("  get <file>      - Read output")