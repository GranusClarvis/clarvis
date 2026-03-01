# Bundle T: Plugin & Configuration Patterns

**Date**: 2026-02-27
**Topics**: Swappable component patterns, Interface-driven plugin systems, Configuration-driven orchestration (YAML)
**Theme**: How modular, declarative architecture enables runtime flexibility in autonomous agent systems

---

## Topic 1: Swappable Component Patterns (Runtime/Agent/Tracker)

### Core Ideas

1. **Registry Pattern over If/Else Chains**: Instead of conditional routing logic (e.g., Clarvis's `task_router.py` with hardcoded `TIER_BOUNDARIES` and `FORCE_CLAUDE_PATTERNS`), a Registry separates *lookup* (mapping keys to implementations) from *routing* (business rules choosing which key). This gives O(1) dispatch with clean extensibility — new handlers are added without modifying core routing code.

2. **Runtime Strategy Swapping**: The Strategy Pattern enables live-swapping of algorithm implementations at runtime. Combined with feature flags or config-driven selection, this enables switching between execution backends (e.g., M2.5 vs Claude Code vs Gemini) without restarts. External config (file/DB) should be source of truth — in-memory registry state is lost on reboot.

3. **`__init_subclass__` Auto-Registration**: Python 3.6+ provides a clean mechanism where subclasses automatically register themselves into a parent class's registry upon definition. Pattern: `class Circle(BaseShape, key="circle")` triggers `BaseShape.__init_subclass__` which adds to a global registry. Caution: explicit registration functions are preferred for debuggability over "magic" auto-registration.

### Key Pattern

```python
class Registry:
    _store: dict[str, type] = {}
    def register(self, key, cls): self._store[key] = cls
    def get(self, key): return self._store[key]
    def unregister(self, key): del self._store[key]
```

---

## Topic 2: Interface-Driven Plugin Systems

### Core Ideas

1. **ABC vs Protocol — Two Paradigms**: Abstract Base Classes (nominal typing: "you declare you *are* something by inheriting") enforce contracts at instantiation time. Protocols (structural typing: "you *are* something if you look like it") enforce contracts at type-check time without requiring inheritance. For plugin architectures in autonomous systems, Protocols fit the "ports and adapters" pattern better — plugins don't need to know about the base class.

2. **Plugin Lifecycle Contract**: Production plugin systems define a standard lifecycle interface:
   - `name`, `version` properties (identity)
   - `initialize(config)` (setup with injected configuration)
   - `execute(context)` (main processing)
   - `cleanup()` (graceful teardown)
   This ensures isolation: one bad plugin cannot crash the host system.

3. **Discovery Mechanisms**: Three approaches ranked by coupling:
   - **File system scanning**: `pathlib.glob("plugins/*.py")` → `importlib` dynamic loading (loosest coupling)
   - **Entry points**: `pyproject.toml` `[project.entry-points."myapp.plugins"]` (package-level, pip-distributed)
   - **Configuration-based**: Explicit listing in config file (most controlled, best for agent systems)

### Key Pattern

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ExecutorPlugin(Protocol):
    name: str
    def initialize(self, config: dict) -> None: ...
    def execute(self, task: str, context: dict) -> dict: ...
    def cleanup(self) -> None: ...
```

---

## Topic 3: Configuration-Driven Orchestration (YAML)

### Core Ideas

1. **Workflows as Data, Not Code**: A declarative DSL (PayPal/academic research, Dec 2025) treats agent workflows as DAG configurations rather than imperative programs. Pipelines compile to JSON Intermediate Representation, enabling cross-language execution (Python, Java, Go) and version control of agent behavior. Production results: **67% reduction in development time**, **74% code reduction** (850→220 LOC), **11% higher task success rate**.

2. **Hot-Reload Without Restart**: Declarative pipelines stored externally can be reloaded at runtime without service restarts. This is critical for autonomous agents that run 24/7 — behavior changes (new cron tasks, modified routing rules, updated prompts) can be deployed as config changes rather than code deployments.

3. **Microsoft Agent Framework (Oct 2025)**: Merges AutoGen's multi-agent orchestration with Semantic Kernel's production foundations. Declarative agents use YAML/JSON to specify prompts, roles, tools — files that can be version-controlled, templatized, and shared. Demonstrates the industry shift toward treating agent orchestration as configuration rather than application programming.

### Key Pattern

```yaml
# Declarative pipeline node (conceptual)
pipeline:
  name: heartbeat_task
  nodes:
    - id: classify
      type: task_router
      config:
        model: minimax-m2.5
        tier_threshold: 0.40
    - id: execute
      type: executor
      depends_on: [classify]
      config:
        strategy: "${classify.output.tier}"
        timeout: 1200
```

---

## Cross-Topic Connections

### Emerging Pattern: The Plugin-Config-Strategy Triangle

All three topics converge on a single architectural insight: **separate what (interface) from which (registry) from how (config)**:

1. **Interface** (Plugin System) defines the contract — what any executor/tracker/agent must implement
2. **Registry** (Swappable Components) maps identifiers to concrete implementations — which implementation to use
3. **Configuration** (YAML Orchestration) drives selection and parameterization — how to wire it all together at runtime

This triangle enables systems that are simultaneously:
- **Extensible** (add new implementations without modifying core code)
- **Configurable** (change behavior via config, not code changes)
- **Observable** (registry provides introspection of all registered components)

### Relevance to Autonomous Agent Systems

The current Clarvis architecture uses hardcoded routing (task_router.py with regex patterns), direct imports between scripts (brain.py as monolithic hub), and script-level orchestration (cron_autonomous.sh with inline prompts). The Plugin-Config-Strategy pattern suggests an evolution path:

- **task_router.py** → Registry of ExecutorPlugins (M2.5, Claude Code, Gemini, local Ollama) selected by config
- **cron schedule** → YAML-defined pipeline DAG with hot-reload (change heartbeat timing without editing crontab)
- **brain.py collections** → Plugin-based memory backends discoverable at runtime

---

## Implementation Ideas for Clarvis

### 1. ExecutorRegistry for Task Router (Medium effort, high impact)

Replace the hardcoded tier boundaries and model lists in `task_router.py` with a Registry pattern:

```python
@runtime_checkable
class Executor(Protocol):
    name: str
    cost_per_1m: float
    def can_handle(self, task_class: str) -> bool: ...
    def execute(self, task: str, context: dict) -> dict: ...

class ExecutorRegistry:
    _executors: dict[str, Executor] = {}

    def register(self, executor: Executor):
        self._executors[executor.name] = executor

    def route(self, task_class: str) -> Executor:
        for ex in sorted(self._executors.values(), key=lambda e: e.cost_per_1m):
            if ex.can_handle(task_class):
                return ex
        return self._executors["claude-code"]  # fallback
```

Benefits: new models added by writing a small class + registering it; cost-based routing without modifying core logic; runtime swapping when a model is down or over-budget.

### 2. YAML-Driven Heartbeat Pipeline (Higher effort, transformative)

Define the heartbeat pipeline (gate → preflight → execute → postflight) as a YAML DAG rather than shell script orchestration. This enables:
- Adding/removing pipeline steps without code changes
- A/B testing different pipeline configurations
- Version-controlled behavior changes with rollback
- Hot-reload: modify pipeline while cron keeps running

---

## Sources

- [Runtime-Swappable Strategy Architecture for LLM Systems](https://levelup.gitconnected.com/how-to-build-runtime-swappable-strategy-architecture-for-llm-powered-recommendation-systems-c6efb7a6267e) (Jan 2026)
- [Python Registry Pattern: Clean Alternative to Factory Classes](https://dev.to/dentedlogic/stop-writing-giant-if-else-chains-master-the-python-registry-pattern-ldm) (2025)
- [How to Build Plugin Systems in Python](https://oneuptime.com/blog/post/2026-01-30-python-plugin-systems/view) (Jan 2026)
- [Declarative Language for LLM Agent Workflows](https://arxiv.org/html/2512.19769) (Dec 2025, PayPal)
- [Microsoft Agent Framework](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/) (Oct 2025)
- [Python abc — Abstract Base Classes](https://docs.python.org/3/library/abc.html)
- [Modern Python Interfaces: ABC, Protocol, or Both?](https://tconsta.medium.com/python-interfaces-abc-protocol-or-both-3c5871ea6642) (2025)
