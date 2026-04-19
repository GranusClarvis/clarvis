"""Brain graph operations — relationship storage, traversal, backfill, decay.

Primary backend: SQLite (via GraphStoreSQLite), default since 2026-03-29 cutover.
JSON backend retained as fallback for environments without SQLite migration.
When backend=sqlite: reads/writes use SQLite exclusively.
When backend=json: reads/writes use JSON (legacy behavior).
"""

import json
import logging
import math
import os
import random
import fcntl
from datetime import datetime, timezone

_log = logging.getLogger("clarvis.brain.graph")

from .constants import MEMORIES, GOALS, PROCEDURES, DEFAULT_COLLECTIONS


class GraphMixin:
    """Graph operations for ClarvisBrain (mixed into the main class)."""

    def _load_graph(self):
        """Load relationship graph.

        When backend=sqlite: initializes SQLite store, skips JSON loading.
        When backend=json: loads JSON with corruption recovery.
        self.graph dict is always populated (empty when SQLite-only) for
        code that reads self.graph directly (e.g. bulk_cross_link edge sets).
        """
        # --- SQLite backend init ---
        self._sqlite_store = None
        backend = getattr(self, 'graph_backend', 'sqlite')
        if backend == 'sqlite':
            sqlite_path = getattr(self, 'graph_sqlite_file', None)
            if sqlite_path:
                try:
                    from .graph_store_sqlite import GraphStoreSQLite
                    self._sqlite_store = GraphStoreSQLite(sqlite_path)
                    _log.info("SQLite graph store initialized: %s", sqlite_path)
                except Exception as exc:
                    _log.error("Failed to initialize SQLite graph store: %s — "
                               "falling back to JSON", exc)

        if self._sqlite_store is not None:
            # SQLite is authoritative — populate self.graph lazily only when
            # code accesses it directly. Start with empty dict.
            self.graph = {"nodes": {}, "edges": []}
            return

        # --- JSON load (fallback when SQLite not available) ---
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    self.graph = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                actual_edges = len(self.graph.get("edges", []))
                expected_edges = self.graph.get("_edge_count")
                if expected_edges is not None and actual_edges != expected_edges:
                    _log.warning(
                        "Graph integrity mismatch: expected %d edges, found %d — "
                        "possible silent corruption in %s",
                        expected_edges, actual_edges, self.graph_file
                    )
                else:
                    _log.debug("Graph loaded: %d edges (integrity OK)", actual_edges)
            except (json.JSONDecodeError, IOError, OSError):
                broken_path = self.graph_file + ".broken"
                os.rename(self.graph_file, broken_path)
                _log.warning("Graph file corrupt, moved to %s — attempting recovery",
                             broken_path)
                try:
                    with open(broken_path, 'r') as f:
                        raw = f.read()
                    last_brace = raw.rfind('},')
                    if last_brace > 0:
                        valid = raw[:last_brace+1] + '\n  ]\n}'
                        self.graph = json.loads(valid)
                        self._save_graph()
                        _log.info("Graph recovered from corruption (%d edges)",
                                  len(self.graph.get("edges", [])))
                    else:
                        self.graph = {"nodes": {}, "edges": []}
                except Exception:
                    self.graph = {"nodes": {}, "edges": []}
        else:
            self.graph = {"nodes": {}, "edges": []}

    def _force_save_graph(self):
        """Save graph WITHOUT merge — used by pruning operations that intentionally remove edges.

        No-op when SQLite backend is active (JSON is archival).
        """
        if self._sqlite_store is not None:
            return
        import tempfile
        self.graph["_edge_count"] = len(self.graph.get("edges", []))
        self.graph["_last_synced"] = datetime.now(timezone.utc).isoformat()
        try:
            dir_path = os.path.dirname(self.graph_file)
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".json.tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(self.graph, f, default=str)
            os.replace(tmp_path, self.graph_file)
        except (IOError, OSError) as exc:
            _log.error("Force save failed: %s", exc)

    def _save_graph(self):
        """Save relationship graph atomically with file locking to prevent race conditions.

        No-op when SQLite backend is active (JSON is archival).
        """
        if self._sqlite_store is not None:
            return
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    on_disk = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                on_disk_edges = {(e['from'], e['to'], e.get('type')) for e in on_disk.get('edges', [])}
                our_edges = {(e['from'], e['to'], e.get('type')) for e in self.graph.get('edges', [])}
                merged_edges = on_disk_edges | our_edges

                if len(merged_edges) > len(our_edges):
                    edge_map = {(e['from'], e['to'], e.get('type')): e for e in self.graph.get('edges', [])}
                    for e in on_disk.get('edges', []):
                        key = (e['from'], e['to'], e.get('type'))
                        if key not in edge_map:
                            edge_map[key] = e
                    self.graph['edges'] = list(edge_map.values())
            except (json.JSONDecodeError, IOError, OSError):
                pass

        # Write edge-count header for integrity verification on next load
        self.graph["_edge_count"] = len(self.graph.get("edges", []))

        tmp_path = f"{self.graph_file}.tmp.{os.getpid()}"
        with open(tmp_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(self.graph, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, self.graph_file)

    def _dual_write_enabled(self) -> bool:
        """Legacy dual-write check. Always False after 2026-03-29 cutover."""
        return os.environ.get("CLARVIS_GRAPH_DUAL_WRITE", "0") != "0"

    def add_relationship(self, from_id, to_id, relationship_type,
                         source_collection=None, target_collection=None):
        """Add a relationship between two memories.

        When SQLite is active: writes SQLite only.
        When JSON fallback: writes JSON.
        """
        now_str = datetime.now(timezone.utc).isoformat()

        edge = {
            "from": from_id,
            "to": to_id,
            "type": relationship_type,
            "created_at": now_str,
        }
        if source_collection:
            edge["source_collection"] = source_collection
        if target_collection:
            edge["target_collection"] = target_collection

        # Write to SQLite when available
        if self._sqlite_store is not None:
            try:
                src_col = source_collection or self._infer_collection(from_id)
                tgt_col = target_collection or self._infer_collection(to_id)
                self._sqlite_store.add_node(from_id, src_col, now_str)
                self._sqlite_store.add_node(to_id, tgt_col, now_str)
                self._sqlite_store.add_edge(
                    from_id, to_id, relationship_type,
                    created_at=now_str,
                    source_collection=source_collection,
                    target_collection=target_collection,
                )
            except Exception as exc:
                _log.warning("SQLite write failed for edge %s->%s: %s",
                             from_id, to_id, exc)
            return edge

        # JSON fallback (no SQLite store available)
        if from_id not in self.graph["nodes"]:
            self.graph["nodes"][from_id] = {
                "collection": source_collection or self._infer_collection(from_id),
                "added_at": now_str,
            }
        if to_id not in self.graph["nodes"]:
            self.graph["nodes"][to_id] = {
                "collection": target_collection or self._infer_collection(to_id),
                "added_at": now_str,
            }

        for existing in self.graph["edges"]:
            if (existing["from"] == from_id and
                    existing["to"] == to_id and
                    existing["type"] == relationship_type):
                return existing

        self.graph["edges"].append(edge)
        self._save_graph()
        return edge

    def _infer_collection(self, memory_id):
        """Infer which collection a memory ID belongs to."""
        for col_name in self.collections:
            if memory_id.startswith(col_name):
                return col_name
        prefix = memory_id.split("_")[0].split("-")[0]
        prefix_map = {
            "proc": PROCEDURES,
            "bridge": MEMORIES,
            "sbridge": MEMORIES,
            "goal": GOALS,
            "mem": MEMORIES,
        }
        return prefix_map.get(prefix, "unknown")

    def get_related(self, memory_id, depth=1):
        """Get memories related to a given memory.

        Uses SQLite indexed lookups when backend=sqlite, else JSON scan.
        """
        if self._sqlite_store is not None:
            return self._sqlite_store.get_related(memory_id, depth)

        # JSON fallback
        related = []
        visited = set()

        def traverse(node_id, current_depth):
            if current_depth > depth or node_id in visited:
                return
            visited.add(node_id)

            for edge in self.graph["edges"]:
                if edge["from"] == node_id:
                    related.append({
                        "id": edge["to"],
                        "relationship": edge["type"],
                        "depth": current_depth
                    })
                    traverse(edge["to"], current_depth + 1)
                elif edge["to"] == node_id:
                    related.append({
                        "id": edge["from"],
                        "relationship": f"inverse-{edge['type']}",
                        "depth": current_depth
                    })
                    traverse(edge["from"], current_depth + 1)

        traverse(memory_id, 1)
        return related

    def backfill_graph_nodes(self):
        """Register nodes referenced by edges but missing from the nodes dict.

        When SQLite is active, backfill is handled by graph_compaction.py
        directly via SQL. This method operates on self.graph (JSON fallback).
        """
        if self._sqlite_store is not None:
            # Backfill in SQLite is done via compaction SQL, not in-memory.
            return 0

        backfilled = 0
        for edge in self.graph.get("edges", []):
            for key in ("from", "to"):
                node_id = edge.get(key)
                if node_id and node_id not in self.graph["nodes"]:
                    collection = edge.get(f"{'source' if key == 'from' else 'target'}_collection")
                    col = collection or self._infer_collection(node_id)
                    now_str = datetime.now(timezone.utc).isoformat()
                    self.graph["nodes"][node_id] = {
                        "collection": col,
                        "added_at": now_str,
                        "backfilled": True,
                    }
                    backfilled += 1
        if backfilled > 0:
            self._save_graph()
        return backfilled

    # Synonym groups for cross-collection matching: when a memory contains
    # terms from one group, also query using terms from related groups.
    _SYNONYM_GROUPS = [
        {"brain", "memory", "chromadb", "vector", "embedding", "recall", "store"},
        {"goal", "objective", "target", "milestone", "deliverable", "outcome"},
        {"procedure", "workflow", "pipeline", "process", "routine", "recipe"},
        {"infrastructure", "system", "server", "cron", "service", "gateway"},
        {"learning", "insight", "lesson", "pattern", "discovery", "finding"},
        {"episode", "task", "heartbeat", "execution", "run", "attempt"},
        {"context", "environment", "config", "setting", "parameter"},
        {"cost", "budget", "spending", "token", "usage", "pricing"},
        {"performance", "latency", "speed", "benchmark", "metric"},
        {"identity", "self", "clarvis", "agent", "persona", "role"},
    ]

    def _synonym_expand(self, text):
        """Generate synonym-expanded query variants for better cross-collection matching."""
        text_lower = text.lower()
        expansions = []
        for group in self._SYNONYM_GROUPS:
            hits = [w for w in group if w in text_lower]
            if hits:
                # Add remaining synonyms as expansion terms
                remaining = group - set(hits)
                if remaining:
                    expansions.extend(list(remaining)[:3])
        if not expansions:
            return None
        # Return original text augmented with synonym terms
        return text[:200] + " " + " ".join(expansions[:8])

    def _existing_edge_pairs(self, edge_type: str) -> set:
        """Get set of (from, to) pairs for a given edge type, from whichever backend is active."""
        pairs = set()
        if self._sqlite_store is not None:
            rows = self._sqlite_store.get_edges(edge_type=edge_type)
            for r in rows:
                pairs.add((r["from_id"], r["to_id"]))
                pairs.add((r["to_id"], r["from_id"]))
        else:
            for e in self.graph.get("edges", []):
                if e.get("type") == edge_type:
                    pairs.add((e["from"], e["to"]))
                    pairs.add((e["to"], e["from"]))
        return pairs

    def _edge_type_counts_by_collection(self, edge_type: str) -> dict:
        """Count edges of a given type per collection, from whichever backend is active."""
        counts = {}
        if self._sqlite_store is not None:
            rows = self._sqlite_store.get_edges(edge_type=edge_type)
            for r in rows:
                src = r.get("source_collection", "")
                tgt = r.get("target_collection", "")
                counts[src] = counts.get(src, 0) + 1
                counts[tgt] = counts.get(tgt, 0) + 1
        else:
            for e in self.graph.get("edges", []):
                if e.get("type") == edge_type:
                    src = e.get("source_collection", "")
                    tgt = e.get("target_collection", "")
                    counts[src] = counts.get(src, 0) + 1
                    counts[tgt] = counts.get(tgt, 0) + 1
        return counts

    def bulk_cross_link(self, max_distance=1.5, max_links_per_memory=3,
                        verbose=False, timeout_seconds=None):
        """Scan all memories and create cross-collection edges where missing.

        Uses synonym-aware matching: when a memory contains domain terms,
        also queries with related synonyms to find bridges that pure embedding
        distance would miss. Under-connected collections get a relaxed distance
        threshold and more links per memory to boost bridge density.

        Args:
            timeout_seconds: If set, stop scanning after this many seconds and
                return partial results. Allows the reflection pipeline to
                proceed even if the full scan can't complete in time.
        """
        import time as _time
        new_edges = 0
        memories_scanned = 0
        timed_out = False
        start_time = _time.monotonic()

        existing_pairs = self._existing_edge_pairs("cross_collection")

        # Count existing cross-collection edges per collection for boost targeting
        col_cross_counts = self._edge_type_counts_by_collection("cross_collection")

        # Under-connected collections get boosted parameters
        median_count = sorted(col_cross_counts.values())[len(col_cross_counts) // 2] if col_cross_counts else 60
        boost_threshold = median_count * 0.7  # collections below 70% of median get a boost

        for col_name, col in self.collections.items():
            is_boosted = col_cross_counts.get(col_name, 0) < boost_threshold
            col_max_distance = max_distance + 0.3 if is_boosted else max_distance
            col_max_links = max_links_per_memory + 2 if is_boosted else max_links_per_memory

            # Check timeout before starting each collection
            if timeout_seconds and (_time.monotonic() - start_time) >= timeout_seconds:
                timed_out = True
                if verbose:
                    print(f"  TIMEOUT after {timeout_seconds}s — stopping crosslink early")
                break

            results = col.get()
            ids = results.get("ids", [])
            docs = results.get("documents", [])

            for idx, (mem_id, doc) in enumerate(zip(ids, docs)):
                if not doc or len(doc) < 10:
                    continue

                # Check timeout every 10 memories to avoid overshoot
                if timeout_seconds and memories_scanned % 10 == 0:
                    if (_time.monotonic() - start_time) >= timeout_seconds:
                        timed_out = True
                        if verbose:
                            print(f"  TIMEOUT after {timeout_seconds}s — stopping crosslink early")
                        break

                memories_scanned += 1
                links_added = 0

                # Build query variants: original + synonym-expanded
                queries = [doc]
                syn_expanded = self._synonym_expand(doc)
                if syn_expanded:
                    queries.append(syn_expanded)

                for other_col_name, other_col in self.collections.items():
                    if other_col_name == col_name:
                        continue
                    if other_col.count() == 0:
                        continue

                    # Query with more results to find better matches
                    n_query = 2 if is_boosted else 1
                    best_matches = []

                    for query_text in queries:
                        try:
                            xresults = other_col.query(
                                query_texts=[query_text],
                                n_results=n_query
                            )
                            if xresults["ids"] and xresults["ids"][0]:
                                for i, (tid, tdist) in enumerate(zip(
                                        xresults["ids"][0], xresults["distances"][0])):
                                    if tdist < col_max_distance and (mem_id, tid) not in existing_pairs:
                                        best_matches.append((tid, tdist, other_col_name))
                        except Exception:
                            continue

                    # Deduplicate and sort by distance
                    seen_targets = set()
                    for tid, tdist, tcol in sorted(best_matches, key=lambda x: x[1]):
                        if tid in seen_targets:
                            continue
                        seen_targets.add(tid)

                        self.add_relationship(mem_id, tid, "cross_collection",
                                              source_collection=col_name, target_collection=tcol)
                        existing_pairs.add((mem_id, tid))
                        existing_pairs.add((tid, mem_id))
                        new_edges += 1
                        links_added += 1

                        if verbose:
                            print(f"  {col_name} -> {tcol} (dist={tdist:.3f}{'*' if is_boosted else ''})")

                        if links_added >= col_max_links:
                            break

                    if links_added >= col_max_links:
                        break

            if timed_out:
                break

            if verbose and ids:
                boost_tag = " [BOOSTED]" if is_boosted else ""
                print(f"  Scanned {col_name}: {len(ids)} memories{boost_tag}")

        elapsed = _time.monotonic() - start_time
        result = {
            "new_edges": new_edges,
            "memories_scanned": memories_scanned,
            "total_edges": (self._sqlite_store.edge_count() if self._sqlite_store
                           else len(self.graph.get("edges", []))),
            "boosted_collections": [c for c, cnt in col_cross_counts.items() if cnt < boost_threshold],
            "timed_out": timed_out,
            "elapsed_seconds": round(elapsed, 1),
        }
        if verbose and timed_out:
            print(f"  Partial scan: {memories_scanned} memories in {elapsed:.0f}s (cap={timeout_seconds}s)")
        return result

    def pair_targeted_cross_link(self, pairs, max_distance=2.0,
                                  max_links_per_memory=10, verbose=False):
        """Densely cross-link a specific list of collection pairs.

        For Phi recovery: targets the lowest-semantic-overlap pairs with
        relaxed distance and higher link density than bulk_cross_link.
        Creates 'semantic_bridge' edges (distinct from bulk_cross_link's
        'cross_collection' edges) so compaction can treat them separately.

        Args:
            pairs: iterable of (col_a, col_b) tuples — order-insensitive.
            max_distance: ChromaDB L2 distance ceiling (default 2.0, quite loose).
            max_links_per_memory: caps links each source memory contributes.
            verbose: print per-pair stats.

        Returns:
            dict with new_edges, pairs_processed, per_pair stats.
        """
        new_edges = 0
        per_pair = {}
        existing = self._existing_edge_pairs("semantic_bridge")
        # Also consult cross_collection edges to avoid duplicate work
        existing_cc = self._existing_edge_pairs("cross_collection")

        for col_a, col_b in pairs:
            if col_a == col_b:
                continue
            ca = self.collections.get(col_a)
            cb = self.collections.get(col_b)
            if ca is None or cb is None or ca.count() == 0 or cb.count() == 0:
                continue

            pair_new = 0
            # bidirectional: a -> b and b -> a
            for src_name, src_col, tgt_name, tgt_col in (
                (col_a, ca, col_b, cb),
                (col_b, cb, col_a, ca),
            ):
                results = src_col.get()
                ids = results.get("ids", [])
                docs = results.get("documents", [])
                for mem_id, doc in zip(ids, docs):
                    if not doc or len(doc) < 10:
                        continue
                    links_added = 0
                    queries = [doc]
                    syn = self._synonym_expand(doc)
                    if syn:
                        queries.append(syn)
                    best = []
                    for q in queries:
                        try:
                            xr = tgt_col.query(
                                query_texts=[q],
                                n_results=min(max_links_per_memory + 2, 10),
                            )
                            if xr["ids"] and xr["ids"][0]:
                                for tid, tdist in zip(
                                        xr["ids"][0], xr["distances"][0]):
                                    if tdist >= max_distance:
                                        continue
                                    if (mem_id, tid) in existing:
                                        continue
                                    if (mem_id, tid) in existing_cc:
                                        continue
                                    best.append((tid, tdist))
                        except Exception:
                            continue
                    seen = set()
                    for tid, tdist in sorted(best, key=lambda x: x[1]):
                        if tid in seen:
                            continue
                        seen.add(tid)
                        self.add_relationship(
                            mem_id, tid, "semantic_bridge",
                            source_collection=src_name,
                            target_collection=tgt_name,
                        )
                        existing.add((mem_id, tid))
                        existing.add((tid, mem_id))
                        new_edges += 1
                        pair_new += 1
                        links_added += 1
                        if links_added >= max_links_per_memory:
                            break
            per_pair[f"{col_a} <-> {col_b}"] = pair_new
            if verbose:
                print(f"  {col_a} <-> {col_b}: +{pair_new} edges")

        return {
            "new_edges": new_edges,
            "pairs_processed": len(per_pair),
            "per_pair": per_pair,
        }

    def bulk_intra_link(self, max_distance=1.2, max_links_per_memory=5,
                        collections=None, verbose=False):
        """Create intra-collection edges between semantically similar memories.

        For each collection, query each memory against the same collection
        to find nearest neighbors, and create 'intra_similar' edges for
        pairs below max_distance. Skips bridge/boost memories.

        Under-connected collections (existing intra-edge count below 70% of
        median) get relaxed distance (+0.4) and more links per memory (+3)
        to boost density where it's most needed.

        Args:
            max_distance: Maximum ChromaDB L2 distance to create an edge (default 1.2).
            max_links_per_memory: Max intra-edges per memory (default 5).
            collections: List of collection names to process (default: all).
            verbose: Print progress.

        Returns:
            dict with new_edges, collections_processed, total_edges.
        """
        new_edges = 0
        collections_processed = 0

        existing_pairs = self._existing_edge_pairs("intra_similar")

        target_collections = collections or list(self.collections.keys())
        now_str = datetime.now(timezone.utc).isoformat()

        # Count existing intra-similar edges per collection for boost targeting
        col_intra_counts = self._edge_type_counts_by_collection("intra_similar")
        if col_intra_counts:
            sorted_counts = sorted(col_intra_counts.values())
            median_count = sorted_counts[len(sorted_counts) // 2]
        else:
            median_count = 60
        boost_threshold = median_count * 0.7

        # Collect for SQLite batch insert
        sqlite_nodes = []
        sqlite_edges = []

        for col_name in target_collections:
            col = self.collections.get(col_name)
            if col is None or col.count() < 3:
                continue

            is_boosted = col_intra_counts.get(col_name, 0) < boost_threshold
            col_max_distance = max_distance + 0.4 if is_boosted else max_distance
            col_max_links = max_links_per_memory + 3 if is_boosted else max_links_per_memory

            collections_processed += 1
            results = col.get(include=["documents"])
            ids = results.get("ids", [])
            docs = results.get("documents", [])

            col_new = 0

            for idx, (mem_id, doc) in enumerate(zip(ids, docs)):
                if not doc or len(doc) < 10:
                    continue
                if mem_id.startswith(("bridge_", "sbridge_", "boost_")):
                    continue

                try:
                    qr = col.query(
                        query_texts=[doc],
                        n_results=min(col_max_links + 1, 12),
                        include=["distances"],
                    )
                except Exception:
                    continue

                if not (qr["ids"] and qr["ids"][0]):
                    continue

                links_added = 0
                for rid, dist in zip(qr["ids"][0], qr["distances"][0]):
                    if rid == mem_id:
                        continue
                    if dist > col_max_distance:
                        break
                    if (mem_id, rid) in existing_pairs:
                        continue

                    sqlite_nodes.append((mem_id, col_name, now_str, 0))
                    sqlite_nodes.append((rid, col_name, now_str, 0))
                    sqlite_edges.append((
                        mem_id, rid, "intra_similar", now_str,
                        col_name, col_name, 1.0,
                    ))
                    existing_pairs.add((mem_id, rid))
                    existing_pairs.add((rid, mem_id))
                    links_added += 1
                    col_new += 1
                    new_edges += 1

                    if links_added >= col_max_links:
                        break

            if verbose:
                suffix = " (boosted)" if is_boosted else ""
                print(f"  {col_name}: {len(ids)} memories, {col_new} new intra-edges{suffix}")

        if new_edges > 0:
            if self._sqlite_store is not None:
                try:
                    if sqlite_nodes:
                        self._sqlite_store.bulk_add_nodes(sqlite_nodes)
                    if sqlite_edges:
                        self._sqlite_store.bulk_add_edges(sqlite_edges)
                except Exception as exc:
                    _log.warning("SQLite write failed for bulk_intra_link: %s", exc)
            else:
                # JSON fallback — build edges in-memory and save
                for (from_id, to_id, etype, created, src_col, tgt_col, _w) in sqlite_edges:
                    self.graph["edges"].append({
                        "from": from_id, "to": to_id,
                        "type": etype, "created_at": created,
                        "source_collection": src_col,
                        "target_collection": tgt_col,
                    })
                self._save_graph()

        total = (self._sqlite_store.edge_count() if self._sqlite_store
                 else len(self.graph.get("edges", [])))
        return {
            "new_edges": new_edges,
            "collections_processed": collections_processed,
            "total_edges": total,
        }

    def decay_edges(self, half_life_days=30, min_weight=0.05, prune_below=0.02,
                    decay_types=None, dry_run=False):
        """Apply age-based exponential decay to edge weights and prune weak edges.

        When SQLite is active, delegates entirely to SQLite store.
        When JSON fallback, operates on self.graph in-memory.

        Args:
            half_life_days: Days for weight to halve (default 30).
            min_weight: Floor — weights below this still participate but are flagged.
            prune_below: Remove edges with decayed weight below this threshold.
            decay_types: Set of edge types to decay (default: hebbian_association only).
            dry_run: If True, compute but don't modify the graph.

        Returns:
            dict: {decayed, pruned, total_before, total_after, avg_weight}
        """
        if decay_types is None:
            decay_types = {"hebbian_association"}

        # SQLite path — delegate entirely
        if self._sqlite_store is not None:
            try:
                return self._sqlite_store.decay_edges(
                    half_life_days=half_life_days,
                    prune_below=prune_below,
                    decay_types=decay_types,
                    dry_run=dry_run,
                )
            except Exception as exc:
                _log.warning("SQLite decay failed: %s", exc)
                return {"decayed": 0, "pruned": 0, "total_before": 0,
                        "total_after": 0, "avg_weight": 0.0}

        # JSON fallback
        now = datetime.now(timezone.utc)
        edges = self.graph.get("edges", [])
        total_before = len(edges)
        decayed_count = 0
        pruned_count = 0
        weights_after = []
        keep = []

        for edge in edges:
            etype = edge.get("type", "unknown")
            if etype not in decay_types:
                keep.append(edge)
                continue

            created_str = edge.get("created_at")
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    age_days = (now - created).total_seconds() / 86400.0
                except (ValueError, TypeError):
                    age_days = 0.0
            else:
                age_days = 0.0

            current_weight = edge.get("weight", 1.0)
            decay_factor = math.pow(2, -age_days / half_life_days)
            new_weight = current_weight * decay_factor

            if new_weight < prune_below:
                pruned_count += 1
                if not dry_run:
                    continue
                else:
                    keep.append(edge)
                    continue
            else:
                decayed_count += 1
                if not dry_run:
                    edge["weight"] = round(new_weight, 6)
                    edge["last_decay"] = now.isoformat()
                weights_after.append(new_weight)
                keep.append(edge)

        if not dry_run and (decayed_count > 0 or pruned_count > 0):
            self.graph["edges"] = keep
            self._save_graph()

        avg_weight = sum(weights_after) / len(weights_after) if weights_after else 0.0

        return {
            "decayed": decayed_count,
            "pruned": pruned_count,
            "total_before": total_before,
            "total_after": len(keep),
            "avg_weight": round(avg_weight, 4),
        }

    def prune_high_degree(self, max_degree=200, weak_types=None, dry_run=False):
        """Prune weak edges from high-degree nodes to reduce graph bloat.

        When SQLite is active, pruning is handled by graph_compaction.py SQL.
        This method operates on self.graph (JSON fallback only).

        Args:
            max_degree: Maximum edges per node (default 200).
            weak_types: Edge types eligible for pruning (default: common weak types).
            dry_run: If True, report what would be pruned without modifying.

        Returns:
            dict: {pruned, nodes_affected, total_before, total_after}
        """
        if self._sqlite_store is not None:
            _log.info("prune_high_degree skipped — use graph_compaction.py for SQLite pruning")
            total = self._sqlite_store.edge_count()
            return {"pruned": 0, "nodes_affected": 0, "total_before": total,
                    "total_after": total, "dry_run": dry_run}

        if weak_types is None:
            weak_types = {
                "cross_collection", "transitive_cross", "hebbian_association",
                "similar_to", "boosted_bridge", "mirror_bridge",
                "semantic_bridge", "bridged_similarity",
            }

        edges = self.graph.get("edges", [])
        total_before = len(edges)

        from collections import defaultdict
        adjacency = defaultdict(list)
        for i, edge in enumerate(edges):
            adjacency[edge.get("from", "")].append((i, edge))
            adjacency[edge.get("to", "")].append((i, edge))

        prune_indices = set()
        nodes_affected = 0

        type_priority = {
            "cross_collection": 0, "transitive_cross": 1,
            "boosted_bridge": 2, "mirror_bridge": 2,
            "semantic_bridge": 3, "bridged_similarity": 3,
            "hebbian_association": 4, "similar_to": 5,
        }

        for node_id, edge_list in adjacency.items():
            if len(edge_list) <= max_degree:
                continue

            nodes_affected += 1

            pruneable = []
            for idx, edge in edge_list:
                etype = edge.get("type", "unknown")
                if etype in weak_types:
                    priority = type_priority.get(etype, 10)
                    weight = edge.get("weight", 0.5)
                    pruneable.append((idx, priority, weight))

            pruneable.sort(key=lambda x: (x[1], x[2]))

            excess = len(edge_list) - max_degree
            for idx, _pri, _wt in pruneable[:excess]:
                prune_indices.add(idx)

        pruned = len(prune_indices)

        if not dry_run and pruned > 0:
            self.graph["edges"] = [e for i, e in enumerate(edges)
                                   if i not in prune_indices]
            self.graph["_edge_count"] = len(self.graph["edges"])
            self._force_save_graph()

        return {
            "pruned": pruned,
            "nodes_affected": nodes_affected,
            "total_before": total_before,
            "total_after": total_before - pruned if not dry_run else total_before,
            "dry_run": dry_run,
        }

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_graph_parity(self, sample_n=100):
        """Verify graph store integrity.

        Post-cutover (2026-03-29): runs SQLite integrity check only.
        JSON parity is no longer checked since JSON is archival.
        Kept for backward compatibility with CLI `clarvis brain graph-verify`.
        """
        if self._sqlite_store is None:
            return {"error": "SQLite store not initialized"}

        sqlite_stats = self._sqlite_store.stats()
        integrity_ok = self._sqlite_store.integrity_check()

        return {
            "sqlite_nodes": sqlite_stats.get("nodes", 0),
            "sqlite_edges": sqlite_stats.get("edges", 0),
            "sqlite_edge_types": sqlite_stats.get("edge_types", {}),
            "integrity_ok": integrity_ok,
            "parity_ok": integrity_ok,  # backward compat
        }
