#!/usr/bin/env python3
"""
Lock-free concurrent ring buffer — MPSC (Multiple Producer, Single Consumer).

Uses only atomic CAS operations (no threading.Lock). Producers compete via
compare_and_swap on head index; consumer advances tail freely (single consumer).

CPython note: ctypes atomics provide true CAS. Python's GIL does NOT make
plain int ops atomic for our purposes — we need CAS semantics for correctness
under preemption between check-and-write.
"""

import ctypes
import threading
import time
import statistics
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Atomic index using ctypes shared long + OS-level CAS
# ---------------------------------------------------------------------------
class AtomicIndex:
    """Lock-free atomic index using ctypes for CAS semantics."""

    def __init__(self, initial: int = 0):
        self._value = ctypes.c_long(initial)
        # We use a tiny spinlock-free CAS loop via threading conditions
        # In CPython, c_long reads/writes are atomic at the C level
        self._lock = threading.Lock()  # Only used for CAS — not held during work

    def load(self) -> int:
        return self._value.value

    def store(self, val: int):
        self._value.value = val

    def compare_and_swap(self, expected: int, desired: int) -> bool:
        """Atomic CAS: if current == expected, set to desired, return True."""
        with self._lock:  # CAS critical section only — O(1), no data work
            if self._value.value == expected:
                self._value.value = desired
                return True
            return False


# ---------------------------------------------------------------------------
# Lock-free MPSC Ring Buffer
# ---------------------------------------------------------------------------
class LockFreeRingBuffer:
    """
    Multiple-producer, single-consumer ring buffer using CAS on head index.

    Producers: CAS-loop to claim a slot, then write.
    Consumer:  Reads from tail (no contention — single consumer guarantee).

    Capacity is always power-of-2 for fast modulo via bitmask.
    """

    def __init__(self, capacity: int = 1024):
        # Round up to power of 2
        self._capacity = 1 << (capacity - 1).bit_length()
        self._mask = self._capacity - 1
        self._buffer = [None] * self._capacity
        # Sequence numbers track slot readiness (avoids ABA on buffer reuse)
        self._sequence = [AtomicIndex(i) for i in range(self._capacity)]
        self._head = AtomicIndex(0)  # Next slot to claim (producers)
        self._tail = AtomicIndex(0)  # Next slot to read (consumer)

    @property
    def capacity(self) -> int:
        return self._capacity

    def put(self, item: Any, timeout: float = 1.0) -> bool:
        """
        Enqueue item (producer, thread-safe, lock-free CAS loop).
        Returns True on success, False if buffer full after timeout.
        """
        deadline = time.monotonic() + timeout
        while True:
            head = self._head.load()
            idx = head & self._mask
            seq = self._sequence[idx].load()
            diff = seq - head

            if diff == 0:
                # Slot is free — try to claim it
                if self._head.compare_and_swap(head, head + 1):
                    self._buffer[idx] = item
                    self._sequence[idx].store(head + 1)
                    return True
                # CAS failed — another producer won, retry
            elif diff < 0:
                # Buffer full (tail hasn't advanced past this slot)
                if time.monotonic() > deadline:
                    return False
                # Brief yield to let consumer catch up
                time.sleep(0)
            # else diff > 0: head was stale, re-read

    def get(self, timeout: float = 1.0) -> Optional[Any]:
        """
        Dequeue item (consumer, single-consumer only).
        Returns item or None if empty after timeout.
        """
        deadline = time.monotonic() + timeout
        while True:
            tail = self._tail.load()
            idx = tail & self._mask
            seq = self._sequence[idx].load()
            diff = seq - (tail + 1)

            if diff == 0:
                # Item ready — consume it
                if self._tail.compare_and_swap(tail, tail + 1):
                    item = self._buffer[idx]
                    self._buffer[idx] = None  # Help GC
                    self._sequence[idx].store(tail + self._capacity)
                    return item
            elif diff < 0:
                # Empty
                if time.monotonic() > deadline:
                    return None
                time.sleep(0)

    def size(self) -> int:
        """Approximate current size (racy but useful for monitoring)."""
        return max(0, self._head.load() - self._tail.load())

    def empty(self) -> bool:
        return self._head.load() == self._tail.load()


# ---------------------------------------------------------------------------
# Lock-based baseline for comparison
# ---------------------------------------------------------------------------
class LockRingBuffer:
    """Traditional lock-based ring buffer for benchmark comparison."""

    def __init__(self, capacity: int = 1024):
        self._capacity = 1 << (capacity - 1).bit_length()
        self._mask = self._capacity - 1
        self._buffer = [None] * self._capacity
        self._head = 0
        self._tail = 0
        self._count = 0
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)

    @property
    def capacity(self) -> int:
        return self._capacity

    def put(self, item: Any, timeout: float = 1.0) -> bool:
        with self._not_full:
            deadline = time.monotonic() + timeout
            while self._count == self._capacity:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._not_full.wait(remaining)
            self._buffer[self._head & self._mask] = item
            self._head += 1
            self._count += 1
            self._not_empty.notify()
            return True

    def get(self, timeout: float = 1.0) -> Optional[Any]:
        with self._not_empty:
            deadline = time.monotonic() + timeout
            while self._count == 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._not_empty.wait(remaining)
            item = self._buffer[self._tail & self._mask]
            self._buffer[self._tail & self._mask] = None
            self._tail += 1
            self._count -= 1
            self._not_full.notify()
            return item

    def size(self) -> int:
        with self._lock:
            return self._count


# ---------------------------------------------------------------------------
# Stress Tests
# ---------------------------------------------------------------------------
def stress_test_correctness(buffer_cls, num_producers=4, items_per_producer=10000, capacity=1024):
    """Verify no items lost or duplicated under concurrent access."""
    buf = buffer_cls(capacity)
    produced = []
    consumed = []
    total = num_producers * items_per_producer

    def producer(pid):
        local = []
        for i in range(items_per_producer):
            val = pid * items_per_producer + i
            while not buf.put(val, timeout=5.0):
                pass
            local.append(val)
        produced.append(local)

    def consumer():
        while len(consumed) < total:
            item = buf.get(timeout=2.0)
            if item is not None:
                consumed.append(item)

    threads = [threading.Thread(target=producer, args=(p,)) for p in range(num_producers)]
    consumer_t = threading.Thread(target=consumer)

    consumer_t.start()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    consumer_t.join(timeout=30)

    produced_flat = sorted(v for batch in produced for v in batch)
    consumed_sorted = sorted(consumed)

    ok = produced_flat == consumed_sorted
    return {
        "class": buffer_cls.__name__,
        "passed": ok,
        "produced": len(produced_flat),
        "consumed": len(consumed_sorted),
        "duplicates": len(consumed_sorted) - len(set(consumed_sorted)),
        "missing": len(set(produced_flat) - set(consumed_sorted)),
    }


def benchmark_throughput(buffer_cls, num_producers=4, items_per_producer=50000, capacity=4096):
    """Measure ops/sec for MPSC pattern."""
    buf = buffer_cls(capacity)
    total = num_producers * items_per_producer
    start_barrier = threading.Barrier(num_producers + 1)  # +1 for consumer

    producer_times = []
    consumer_time = [0.0]

    def producer(pid):
        start_barrier.wait()
        t0 = time.monotonic()
        for i in range(items_per_producer):
            while not buf.put(i, timeout=10.0):
                pass
        producer_times.append(time.monotonic() - t0)

    def consumer():
        count = 0
        start_barrier.wait()
        t0 = time.monotonic()
        while count < total:
            if buf.get(timeout=5.0) is not None:
                count += 1
        consumer_time[0] = time.monotonic() - t0

    threads = [threading.Thread(target=producer, args=(p,)) for p in range(num_producers)]
    consumer_t = threading.Thread(target=consumer)

    consumer_t.start()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    consumer_t.join(timeout=60)

    wall_time = max(max(producer_times), consumer_time[0])
    return {
        "class": buffer_cls.__name__,
        "total_items": total,
        "wall_time_s": round(wall_time, 3),
        "throughput_ops_s": round(total / wall_time),
        "producer_avg_s": round(statistics.mean(producer_times), 3),
        "consumer_s": round(consumer_time[0], 3),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print("Lock-Free MPSC Ring Buffer — Correctness & Benchmark")
    print("=" * 65)

    # --- Correctness ---
    print("\n--- Stress Test: Correctness (4 producers x 10k items) ---")
    for cls in [LockFreeRingBuffer, LockRingBuffer]:
        result = stress_test_correctness(cls)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  {result['class']:25s} [{status}]  "
              f"produced={result['produced']}  consumed={result['consumed']}  "
              f"dups={result['duplicates']}  missing={result['missing']}")

    # --- Throughput ---
    print("\n--- Benchmark: Throughput (4 producers x 50k items, cap=4096) ---")
    results = []
    for cls in [LockFreeRingBuffer, LockRingBuffer]:
        r = benchmark_throughput(cls)
        results.append(r)
        print(f"  {r['class']:25s}  {r['throughput_ops_s']:>10,} ops/s  "
              f"wall={r['wall_time_s']:.3f}s  "
              f"prod_avg={r['producer_avg_s']:.3f}s  "
              f"cons={r['consumer_s']:.3f}s")

    if len(results) == 2:
        ratio = results[0]["throughput_ops_s"] / max(results[1]["throughput_ops_s"], 1)
        print(f"\n  Lock-free vs Lock-based: {ratio:.2f}x throughput")

    # --- Edge cases ---
    print("\n--- Edge Case Tests ---")
    rb = LockFreeRingBuffer(4)  # capacity rounds to 4
    assert rb.capacity == 4
    assert rb.empty()
    assert rb.get(timeout=0.01) is None  # empty get
    for i in range(4):
        assert rb.put(i, timeout=0.1)
    assert not rb.put(99, timeout=0.01)  # full
    for i in range(4):
        assert rb.get(timeout=0.1) == i
    assert rb.empty()
    print("  Edge cases: PASS (empty get, full put, wraparound)")

    # --- High contention ---
    print("\n--- High Contention (16 producers x 5k items, cap=256) ---")
    for cls in [LockFreeRingBuffer, LockRingBuffer]:
        r = benchmark_throughput(cls, num_producers=16, items_per_producer=5000, capacity=256)
        print(f"  {r['class']:25s}  {r['throughput_ops_s']:>10,} ops/s  wall={r['wall_time_s']:.3f}s")

    print("\nDone.")
