#!/usr/bin/env python3
"""
Challenge: coding-challenge-06
Persistent (immutable) skip list with O(log n) search, insert, delete.

Approach: full-path cloning at each level — clone every node from head to the
update point so that new versions are fully isolated from old ones.
Average O(log^2 n) per mutation, O(log n) search.
"""

import random
import time
from typing import Optional, List, Tuple, Any

SENTINEL_KEY = float("-inf")


class SkipNode:
    __slots__ = ("key", "value", "forward")

    def __init__(self, key: Any, value: Any, level: int):
        self.key = key
        self.value = value
        self.forward: List[Optional["SkipNode"]] = [None] * level

    @property
    def level(self) -> int:
        return len(self.forward)


def _random_level(max_level: int, p: float = 0.5) -> int:
    lv = 1
    while random.random() < p and lv < max_level:
        lv += 1
    return lv


class SkipList:
    __slots__ = ("_head", "_size", "_version", "_max_level")

    def __init__(self, head: SkipNode, size: int, version: int, max_level: int):
        self._head = head
        self._size = size
        self._version = version
        self._max_level = max_level

    @property
    def size(self) -> int:
        return self._size

    @property
    def version(self) -> int:
        return self._version

    def search(self, key) -> Optional[Any]:
        node = self._head
        for i in range(self._max_level - 1, -1, -1):
            while i < node.level and node.forward[i] is not None and node.forward[i].key < key:
                node = node.forward[i]
        nxt = node.forward[0] if node.level > 0 else None
        return nxt.value if nxt is not None and nxt.key == key else None

    def _collect_paths(self, key):
        """Collect full traversal paths at each level from head to the update node."""
        paths = [[] for _ in range(self._max_level)]
        update = [None] * self._max_level
        node = self._head
        for i in range(self._max_level - 1, -1, -1):
            paths[i].append(node)
            while i < node.level and node.forward[i] is not None and node.forward[i].key < key:
                node = node.forward[i]
                paths[i].append(node)
            update[i] = node
        return paths, update

    def _clone_and_rewire(self, paths, update, max_level_affected, modify_fn):
        """Clone all nodes on paths and apply modify_fn to the last node at each level."""
        clones = {}

        def get_clone(orig):
            oid = id(orig)
            if oid not in clones:
                c = SkipNode(orig.key, orig.value, orig.level)
                c.forward = list(orig.forward)
                clones[oid] = c
            return clones[oid]

        for i in range(max_level_affected):
            for node in paths[i]:
                get_clone(node)

        modify_fn(clones, update, get_clone)

        for c in clones.values():
            for j in range(c.level):
                if c.forward[j] is not None and id(c.forward[j]) in clones:
                    c.forward[j] = clones[id(c.forward[j])]

        return get_clone(self._head)

    def insert(self, key, value) -> "SkipList":
        paths, update = self._collect_paths(key)

        nxt = update[0].forward[0] if update[0].level > 0 else None
        if nxt is not None and nxt.key == key:
            def do_update(clones, upd, get_clone):
                target_clone = get_clone(nxt)
                target_clone.value = value
            new_head = self._clone_and_rewire(paths, update, self._max_level, do_update)
            return SkipList(new_head, self._size, self._version + 1, self._max_level)

        new_level = _random_level(self._max_level)
        new_node = SkipNode(key, value, new_level)

        def do_insert(clones, upd, get_clone):
            for i in range(new_level):
                u = get_clone(upd[i])
                new_node.forward[i] = u.forward[i]
                u.forward[i] = new_node

        new_head = self._clone_and_rewire(paths, update, self._max_level, do_insert)
        return SkipList(new_head, self._size + 1, self._version + 1, self._max_level)

    def delete(self, key) -> "SkipList":
        paths, update = self._collect_paths(key)

        target = update[0].forward[0] if update[0].level > 0 else None
        if target is None or target.key != key:
            return self

        def do_delete(clones, upd, get_clone):
            for i in range(target.level):
                if i < upd[i].level and upd[i].forward[i] is target:
                    u = get_clone(upd[i])
                    u.forward[i] = target.forward[i]

        new_head = self._clone_and_rewire(paths, update, self._max_level, do_delete)
        return SkipList(new_head, self._size - 1, self._version + 1, self._max_level)

    def to_list(self) -> List[Tuple[Any, Any]]:
        result = []
        node = self._head.forward[0] if self._head.level > 0 else None
        while node is not None:
            result.append((node.key, node.value))
            node = node.forward[0] if node.level > 0 else None
        return result

    def __contains__(self, key) -> bool:
        return self.search(key) is not None

    def __len__(self) -> int:
        return self._size


def create(max_level: int = 16) -> SkipList:
    head = SkipNode(SENTINEL_KEY, None, max_level)
    return SkipList(head, 0, 0, max_level)


class VersionHistory:
    def __init__(self, max_level: int = 16):
        self._versions: List[SkipList] = [create(max_level)]

    @property
    def current(self) -> SkipList:
        return self._versions[-1]

    def insert(self, key, value) -> SkipList:
        new = self.current.insert(key, value)
        self._versions.append(new)
        return new

    def delete(self, key) -> SkipList:
        new = self.current.delete(key)
        self._versions.append(new)
        return new

    def at_version(self, v: int) -> SkipList:
        if 0 <= v < len(self._versions):
            return self._versions[v]
        raise IndexError(f"Version {v} not found (0-{len(self._versions)-1})")

    @property
    def version_count(self) -> int:
        return len(self._versions)


# --- Tests ---

def test_basic():
    random.seed(1)
    vh = VersionHistory()
    vh.insert(5, "five")
    vh.insert(3, "three")
    vh.insert(7, "seven")
    vh.insert(1, "one")

    assert vh.current.search(5) == "five"
    assert vh.current.search(3) == "three"
    assert vh.current.search(7) == "seven"
    assert vh.current.search(1) == "one"
    assert vh.current.search(99) is None
    assert len(vh.current) == 4
    print(f"  basic: OK (versions={vh.version_count}, size={len(vh.current)})")


def test_persistence():
    random.seed(2)
    vh = VersionHistory()
    for i in range(20):
        vh.insert(i, f"val_{i}")

    v10 = vh.at_version(10)
    assert len(v10) == 10
    for i in range(10):
        assert v10.search(i) == f"val_{i}", f"v10 missing key {i}"
    assert v10.search(15) is None

    assert len(vh.current) == 20
    assert vh.current.search(15) == "val_15"
    print(f"  persistence: OK ({vh.version_count} versions)")


def test_delete():
    random.seed(3)
    vh = VersionHistory()
    for i in [10, 20, 30, 40, 50]:
        vh.insert(i, i * 10)

    pre_v = vh.version_count - 1
    vh.delete(30)

    assert vh.current.search(30) is None
    assert vh.current.search(10) == 100
    assert vh.current.search(50) == 500
    assert vh.at_version(pre_v).search(30) == 300
    print(f"  delete: OK")


def test_update():
    random.seed(4)
    vh = VersionHistory()
    vh.insert(5, "original")
    v1 = vh.version_count - 1
    vh.insert(5, "updated")

    assert vh.current.search(5) == "updated"
    assert vh.at_version(v1).search(5) == "original"
    print(f"  update: OK")


def test_ordering():
    random.seed(5)
    vh = VersionHistory()
    for k in [50, 10, 30, 20, 40]:
        vh.insert(k, k)

    keys = [k for k, v in vh.current.to_list()]
    assert keys == sorted(keys), f"got {keys}"
    print(f"  ordering: OK ({keys})")


def test_many_versions():
    random.seed(6)
    vh = VersionHistory()
    for i in range(100):
        vh.insert(i, i)

    for v in [10, 50, 99]:
        sl = vh.at_version(v + 1)
        assert len(sl) == v + 1
        for j in range(v + 1):
            assert sl.search(j) == j, f"v{v+1} missing {j}"
    print(f"  many_versions: OK ({vh.version_count} versions)")


def test_delete_persistence():
    random.seed(7)
    vh = VersionHistory()
    for i in range(10):
        vh.insert(i, i)

    v_before = vh.version_count - 1
    vh.delete(5)
    vh.delete(3)
    vh.delete(7)

    assert len(vh.current) == 7
    assert vh.current.search(5) is None
    assert vh.current.search(3) is None
    assert vh.current.search(7) is None
    assert vh.current.search(0) == 0
    assert vh.current.search(9) == 9

    full = vh.at_version(v_before)
    for i in range(10):
        assert full.search(i) == i
    print(f"  delete_persistence: OK")


def benchmark():
    random.seed(42)
    n = 5000
    vh = VersionHistory()

    t0 = time.monotonic()
    for i in range(n):
        vh.insert(random.randint(0, 100000), i)
    insert_time = time.monotonic() - t0

    t0 = time.monotonic()
    hits = 0
    for _ in range(n):
        if vh.current.search(random.randint(0, 100000)) is not None:
            hits += 1
    search_time = time.monotonic() - t0

    print(f"  benchmark ({n} ops):")
    print(f"    insert: {insert_time:.3f}s ({n/insert_time:.0f} ops/s)")
    print(f"    search: {search_time:.3f}s ({n/search_time:.0f} ops/s, {hits} hits)")
    print(f"    versions: {vh.version_count}, final size: {len(vh.current)}")


if __name__ == "__main__":
    print("Persistent Skip List — coding-challenge-06")
    print("-" * 45)
    test_basic()
    test_persistence()
    test_delete()
    test_update()
    test_ordering()
    test_many_versions()
    test_delete_persistence()
    benchmark()
    print("\nAll tests passed.")
