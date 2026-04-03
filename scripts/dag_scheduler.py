#!/usr/bin/env python3
"""Minimal DAG task scheduler with dependency resolution and parallel execution.

Features:
  - Topological sorting via Kahn's algorithm
  - Cycle detection via iterative DFS (clear error with cycle path)
  - Parallel execution of independent tasks using asyncio
  - Per-task timeout handling
  - Structured result collection with success/error tracking

Usage:
    python3 dag_scheduler.py              # Run built-in demo
    python3 dag_scheduler.py --verbose     # Verbose logging
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class TaskState(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    TIMED_OUT = auto()


@dataclass
class Task:
    """A unit of work in the DAG.

    Args:
        name: Unique task identifier.
        fn: Async callable that performs the work. Receives no arguments;
            use closures or functools.partial to bind state.
        deps: Names of tasks that must complete before this one starts.
        timeout_s: Per-task timeout in seconds. None means no timeout.
    """
    name: str
    fn: Callable[[], Awaitable[Any]]
    deps: list[str] = field(default_factory=list)
    timeout_s: Optional[float] = None


@dataclass
class TaskResult:
    """Outcome of a single task execution."""
    name: str
    state: TaskState
    value: Any = None
    error: Optional[BaseException] = None
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.state == TaskState.COMPLETED

    def __repr__(self) -> str:
        if self.ok:
            return f"TaskResult({self.name!r}, COMPLETED, value={self.value!r}, {self.elapsed_s:.3f}s)"
        return f"TaskResult({self.name!r}, {self.state.name}, error={self.error!r}, {self.elapsed_s:.3f}s)"


class CycleError(Exception):
    """Raised when the task graph contains a cycle."""
    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        path = " -> ".join(cycle)
        super().__init__(f"Cycle detected: {path}")


class DAGScheduler:
    """Schedules and executes a DAG of async tasks with dependency resolution.

    Tasks whose dependencies have all completed are launched in parallel.
    If a dependency fails or times out, dependent tasks are marked FAILED
    with a clear error message (they are not executed).
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    # ── Public API ──────────────────────────────────────────────────

    def add_task(self, task: Task) -> None:
        """Register a task. Raises ValueError on duplicate names."""
        if task.name in self._tasks:
            raise ValueError(f"Duplicate task name: {task.name!r}")
        self._tasks[task.name] = task

    def validate(self) -> list[str]:
        """Validate the DAG: check references and detect cycles.

        Returns:
            A topologically sorted list of task names.

        Raises:
            ValueError: If a dependency references an unknown task.
            CycleError: If the graph contains a cycle (includes the cycle path).
        """
        self._check_refs()
        self._detect_cycles()
        return self._topo_sort()

    async def run(self) -> dict[str, TaskResult]:
        """Validate and execute the DAG.

        Independent tasks run concurrently via asyncio. A task starts only
        after all its dependencies have completed successfully.

        Returns:
            Mapping of task name to TaskResult for every task in the DAG.
        """
        order = self.validate()
        return await self._execute(order)

    # ── Validation internals ────────────────────────────────────────

    def _check_refs(self) -> None:
        """Ensure every dependency name points to a registered task."""
        for task in self._tasks.values():
            for dep in task.deps:
                if dep not in self._tasks:
                    raise ValueError(
                        f"Task {task.name!r} depends on unknown task {dep!r}"
                    )

    def _detect_cycles(self) -> None:
        """DFS cycle detection. Raises CycleError with the exact cycle path."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {name: WHITE for name in self._tasks}

        # Build adjacency: dep -> tasks that depend on it.
        adj: dict[str, list[str]] = defaultdict(list)
        for task in self._tasks.values():
            for dep in task.deps:
                adj[dep].append(task.name)

        def _dfs(node: str, path: list[str]) -> None:
            color[node] = GRAY
            path.append(node)
            for nxt in adj[node]:
                if color[nxt] == GRAY:
                    # Extract the cycle portion from path.
                    idx = path.index(nxt)
                    cycle = path[idx:] + [nxt]
                    raise CycleError(cycle)
                if color[nxt] == WHITE:
                    _dfs(nxt, path)
            path.pop()
            color[node] = BLACK

        for start in self._tasks:
            if color[start] == WHITE:
                _dfs(start, [])

    def _topo_sort(self) -> list[str]:
        """Kahn's algorithm topological sort. Returns list in execution order."""
        in_degree: dict[str, int] = {name: 0 for name in self._tasks}
        dependents: dict[str, list[str]] = defaultdict(list)

        for task in self._tasks.values():
            for dep in task.deps:
                dependents[dep].append(task.name)
                in_degree[task.name] += 1

        queue = deque(
            sorted(name for name, deg in in_degree.items() if deg == 0)
        )
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for child in sorted(dependents[node]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # If not all nodes are in order, there is a cycle (belt-and-suspenders).
        if len(order) != len(self._tasks):
            remaining = set(self._tasks) - set(order)
            raise CycleError(sorted(remaining))

        return order

    # ── Execution engine ────────────────────────────────────────────

    async def _execute(self, order: list[str]) -> dict[str, TaskResult]:
        """Run tasks respecting dependencies, parallelizing where possible."""
        results: dict[str, TaskResult] = {}
        pending_count: dict[str, int] = {}
        dependents: dict[str, list[str]] = defaultdict(list)

        for task in self._tasks.values():
            pending_count[task.name] = len(task.deps)
            for dep in task.deps:
                dependents[dep].append(task.name)

        # Semaphore-free approach: track ready tasks, dispatch as deps finish.
        ready: asyncio.Queue[str] = asyncio.Queue()
        remaining = set(self._tasks.keys())

        # Seed with root tasks (no dependencies).
        for name in order:
            if pending_count[name] == 0:
                await ready.put(name)

        async def _run_task(name: str) -> TaskResult:
            task = self._tasks[name]

            # Check that all dependencies succeeded.
            failed_deps = [
                d for d in task.deps
                if d in results and not results[d].ok
            ]
            if failed_deps:
                return TaskResult(
                    name=name,
                    state=TaskState.FAILED,
                    error=RuntimeError(
                        f"Skipped: upstream task(s) failed: {', '.join(failed_deps)}"
                    ),
                )

            t0 = time.monotonic()
            try:
                if task.timeout_s is not None:
                    value = await asyncio.wait_for(
                        task.fn(), timeout=task.timeout_s
                    )
                else:
                    value = await task.fn()
                elapsed = time.monotonic() - t0
                return TaskResult(
                    name=name,
                    state=TaskState.COMPLETED,
                    value=value,
                    elapsed_s=elapsed,
                )
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - t0
                return TaskResult(
                    name=name,
                    state=TaskState.TIMED_OUT,
                    error=TimeoutError(
                        f"Task {name!r} timed out after {task.timeout_s}s"
                    ),
                    elapsed_s=elapsed,
                )
            except Exception as exc:
                elapsed = time.monotonic() - t0
                return TaskResult(
                    name=name,
                    state=TaskState.FAILED,
                    error=exc,
                    elapsed_s=elapsed,
                )

        active: set[asyncio.Task] = set()

        # Map asyncio.Task -> task name for bookkeeping.
        task_names: dict[asyncio.Task, str] = {}

        def _launch(name: str) -> None:
            logger.info("Launching task %r", name)
            at = asyncio.create_task(_run_task(name))
            task_names[at] = name
            active.add(at)

        # Drain the ready queue and launch initial tasks.
        while not ready.empty():
            _launch(await ready.get())

        while remaining:
            if not active:
                # No active tasks but work remains — should not happen in a
                # valid DAG, but guard against infinite loop.
                for name in list(remaining):
                    results[name] = TaskResult(
                        name=name,
                        state=TaskState.FAILED,
                        error=RuntimeError("Deadlock: no runnable tasks"),
                    )
                    remaining.discard(name)
                break

            done, active = await asyncio.wait(
                active, return_when=asyncio.FIRST_COMPLETED
            )

            for completed_at in done:
                name = task_names.pop(completed_at)
                result = completed_at.result()
                results[name] = result
                remaining.discard(name)

                logger.info(
                    "Task %r finished: %s (%.3fs)",
                    name, result.state.name, result.elapsed_s,
                )

                # Unblock dependents.
                for child in dependents[name]:
                    pending_count[child] -= 1
                    if pending_count[child] == 0 and child in remaining:
                        _launch(child)

            # Also launch anything newly ready from the queue.
            while not ready.empty():
                _launch(await ready.get())

        return results


# ── CLI Demo ────────────────────────────────────────────────────────

def _build_demo_dag() -> DAGScheduler:
    """Build a sample DAG simulating a build/deploy pipeline.

    Graph structure:
        fetch_deps ──┬──> compile ──┬──> link ──> package ──> deploy
                     │              │
        lint ────────┘              └──> test ──────────────────┘
                                          │
        gen_docs ─────────────────────────┘

    fetch_deps and lint and gen_docs run in parallel (no deps).
    compile waits for fetch_deps and lint.
    link and test wait for compile.  gen_docs also feeds test.
    package waits for link.
    deploy waits for package and test.
    """
    scheduler = DAGScheduler()

    async def _sim(label: str, duration: float = 0.3, fail: bool = False) -> str:
        """Simulate work."""
        await asyncio.sleep(duration)
        if fail:
            raise RuntimeError(f"{label} failed!")
        return f"{label}: ok"

    scheduler.add_task(Task(
        name="fetch_deps",
        fn=lambda: _sim("fetch_deps", 0.4),
    ))
    scheduler.add_task(Task(
        name="lint",
        fn=lambda: _sim("lint", 0.2),
    ))
    scheduler.add_task(Task(
        name="gen_docs",
        fn=lambda: _sim("gen_docs", 0.3),
    ))
    scheduler.add_task(Task(
        name="compile",
        fn=lambda: _sim("compile", 0.5),
        deps=["fetch_deps", "lint"],
    ))
    scheduler.add_task(Task(
        name="link",
        fn=lambda: _sim("link", 0.2),
        deps=["compile"],
    ))
    scheduler.add_task(Task(
        name="test",
        fn=lambda: _sim("test", 0.6),
        deps=["compile", "gen_docs"],
    ))
    scheduler.add_task(Task(
        name="package",
        fn=lambda: _sim("package", 0.15),
        deps=["link"],
    ))
    scheduler.add_task(Task(
        name="deploy",
        fn=lambda: _sim("deploy", 0.25),
        deps=["package", "test"],
        timeout_s=5.0,
    ))

    return scheduler


def _build_cycle_dag() -> DAGScheduler:
    """Build a DAG with a cycle for demonstration."""
    scheduler = DAGScheduler()

    async def noop() -> str:
        return "ok"

    scheduler.add_task(Task(name="a", fn=noop, deps=["c"]))
    scheduler.add_task(Task(name="b", fn=noop, deps=["a"]))
    scheduler.add_task(Task(name="c", fn=noop, deps=["b"]))
    return scheduler


def _build_failure_dag() -> DAGScheduler:
    """Build a DAG where an upstream task fails, cascading to dependents."""
    scheduler = DAGScheduler()

    async def _sim(label: str, duration: float = 0.1, fail: bool = False) -> str:
        await asyncio.sleep(duration)
        if fail:
            raise RuntimeError(f"{label} exploded")
        return f"{label}: ok"

    scheduler.add_task(Task(name="setup", fn=lambda: _sim("setup", 0.1)))
    scheduler.add_task(Task(
        name="build",
        fn=lambda: _sim("build", 0.1, fail=True),
        deps=["setup"],
    ))
    scheduler.add_task(Task(name="test", fn=lambda: _sim("test", 0.1), deps=["build"]))
    scheduler.add_task(Task(name="deploy", fn=lambda: _sim("deploy", 0.1), deps=["test"]))
    return scheduler


def _build_timeout_dag() -> DAGScheduler:
    """Build a DAG where a task exceeds its timeout."""
    scheduler = DAGScheduler()

    async def slow() -> str:
        await asyncio.sleep(10.0)
        return "done"

    async def fast() -> str:
        await asyncio.sleep(0.05)
        return "fast: ok"

    scheduler.add_task(Task(name="slow_task", fn=slow, timeout_s=0.3))
    scheduler.add_task(Task(name="after_slow", fn=fast, deps=["slow_task"]))
    return scheduler


async def _run_demo(verbose: bool = False) -> None:
    sep = "-" * 60

    # 1. Normal DAG execution.
    print(f"\n{sep}")
    print("Demo 1: Build/Deploy Pipeline (parallel execution)")
    print(sep)

    scheduler = _build_demo_dag()
    order = scheduler.validate()
    print(f"Topological order: {order}")

    t0 = time.monotonic()
    results = await scheduler.run()
    wall = time.monotonic() - t0
    serial = sum(r.elapsed_s for r in results.values() if r.ok)

    for name in order:
        r = results[name]
        status = "OK" if r.ok else r.state.name
        print(f"  {name:15s} {status:12s} {r.elapsed_s:.3f}s  {r.value or r.error}")
    print(f"Wall time: {wall:.3f}s  |  Serial sum: {serial:.3f}s  |  Speedup: {serial/wall:.1f}x")

    # 2. Cycle detection.
    print(f"\n{sep}")
    print("Demo 2: Cycle Detection")
    print(sep)

    try:
        _build_cycle_dag().validate()
        print("  ERROR: cycle was not detected!")
    except CycleError as e:
        print(f"  Caught CycleError: {e}")

    # 3. Failure cascade.
    print(f"\n{sep}")
    print("Demo 3: Failure Cascade")
    print(sep)

    results = await _build_failure_dag().run()
    for name in ["setup", "build", "test", "deploy"]:
        r = results[name]
        status = "OK" if r.ok else r.state.name
        print(f"  {name:15s} {status:12s} {r.error or r.value}")

    # 4. Timeout handling.
    print(f"\n{sep}")
    print("Demo 4: Timeout Handling")
    print(sep)

    results = await _build_timeout_dag().run()
    for name in ["slow_task", "after_slow"]:
        r = results[name]
        status = "OK" if r.ok else r.state.name
        print(f"  {name:15s} {status:12s} {r.error or r.value}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DAG task scheduler with dependency resolution"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(_run_demo(verbose=args.verbose))


if __name__ == "__main__":
    main()
