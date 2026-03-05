"""Brain graph operations — relationship storage, traversal, backfill, decay.

Supports dual-backend: JSON (legacy) + SQLite (via GraphStoreSQLite).
Backend selection: env CLARVIS_GRAPH_BACKEND=json|sqlite (default: json).
When sqlite: reads use SQLite, writes dual-write to both JSON and SQLite.
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
        """Load relationship graph with corruption recovery + file locking + integrity check.

        Also initializes SQLite store when CLARVIS_GRAPH_BACKEND=sqlite.
        """
        # --- JSON load (always — keeps self.graph populated for compatibility) ---
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    self.graph = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                # Integrity check: verify edge count matches header if present
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

        # --- SQLite backend init (dual-write when enabled) ---
        self._sqlite_store = None
        backend = getattr(self, 'graph_backend', 'json')
        if backend == 'sqlite':
            sqlite_path = getattr(self, 'graph_sqlite_file', None)
            if sqlite_path:
                try:
                    from .graph_store_sqlite import GraphStoreSQLite
                    self._sqlite_store = GraphStoreSQLite(sqlite_path)
                    _log.info("SQLite graph store initialized: %s (dual-write enabled)",
                              sqlite_path)
                except Exception as exc:
                    _log.error("Failed to initialize SQLite graph store: %s", exc)

    def _save_graph(self):
        """Save relationship graph atomically with file locking to prevent race conditions"""
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

        tmp_path = self.graph_file + ".tmp"
        with open(tmp_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(self.graph, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, self.graph_file)

    def add_relationship(self, from_id, to_id, relationship_type,
                         source_collection=None, target_collection=None):
        """Add a relationship between two memories. Dual-writes to SQLite when enabled."""
        now_str = datetime.now(timezone.utc).isoformat()

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

        for existing in self.graph["edges"]:
            if (existing["from"] == from_id and
                    existing["to"] == to_id and
                    existing["type"] == relationship_type):
                return existing

        self.graph["edges"].append(edge)
        self._save_graph()

        # Dual-write to SQLite
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
                _log.warning("SQLite dual-write failed for edge %s->%s: %s",
                             from_id, to_id, exc)

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
        """Register nodes referenced by edges but missing from the nodes dict."""
        backfilled = 0
        sqlite_nodes = []  # Collect for batch SQLite insert
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
                    sqlite_nodes.append((node_id, col, now_str, 1))
                    backfilled += 1
        if backfilled > 0:
            self._save_graph()
            # Dual-write backfilled nodes to SQLite
            if self._sqlite_store is not None and sqlite_nodes:
                try:
                    self._sqlite_store.bulk_add_nodes(sqlite_nodes)
                except Exception as exc:
                    _log.warning("SQLite dual-write failed for backfill: %s", exc)
        return backfilled

    def bulk_cross_link(self, max_distance=1.5, max_links_per_memory=3, verbose=False):
        """Scan all memories and create cross-collection edges where missing."""
        new_edges = 0
        memories_scanned = 0

        existing_pairs = set()
        for e in self.graph.get("edges", []):
            if e.get("type") == "cross_collection":
                existing_pairs.add((e["from"], e["to"]))
                existing_pairs.add((e["to"], e["from"]))

        for col_name, col in self.collections.items():
            results = col.get()
            ids = results.get("ids", [])
            docs = results.get("documents", [])

            for idx, (mem_id, doc) in enumerate(zip(ids, docs)):
                if not doc or len(doc) < 10:
                    continue

                memories_scanned += 1
                links_added = 0

                for other_col_name, other_col in self.collections.items():
                    if other_col_name == col_name:
                        continue
                    if other_col.count() == 0:
                        continue

                    try:
                        xresults = other_col.query(
                            query_texts=[doc],
                            n_results=1
                        )
                        if (xresults["ids"] and xresults["ids"][0] and
                            xresults["distances"] and xresults["distances"][0]):
                            target_id = xresults["ids"][0][0]
                            dist = xresults["distances"][0][0]

                            if dist < max_distance and (mem_id, target_id) not in existing_pairs:
                                self.add_relationship(mem_id, target_id, "cross_collection",
                                                      source_collection=col_name, target_collection=other_col_name)
                                existing_pairs.add((mem_id, target_id))
                                existing_pairs.add((target_id, mem_id))
                                new_edges += 1
                                links_added += 1

                                if verbose:
                                    print(f"  {col_name} -> {other_col_name} (dist={dist:.3f})")

                                if links_added >= max_links_per_memory:
                                    break
                    except Exception:
                        continue

            if verbose and ids:
                print(f"  Scanned {col_name}: {len(ids)} memories")

        return {
            "new_edges": new_edges,
            "memories_scanned": memories_scanned,
            "total_edges": len(self.graph.get("edges", [])),
        }

    def bulk_intra_link(self, max_distance=1.2, max_links_per_memory=5,
                        collections=None, verbose=False):
        """Create intra-collection edges between semantically similar memories.

        For each collection, query each memory against the same collection
        to find nearest neighbors, and create 'intra_similar' edges for
        pairs below max_distance. Skips bridge/boost memories.

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

        # Build existing edge set for fast deduplication
        existing_pairs = set()
        for e in self.graph.get("edges", []):
            if e.get("type") == "intra_similar":
                existing_pairs.add((e["from"], e["to"]))
                existing_pairs.add((e["to"], e["from"]))

        target_collections = collections or list(self.collections.keys())
        now_str = datetime.now(timezone.utc).isoformat()

        # Collect for SQLite batch insert
        sqlite_nodes = []
        sqlite_edges = []

        for col_name in target_collections:
            col = self.collections.get(col_name)
            if col is None or col.count() < 3:
                continue

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
                        n_results=min(max_links_per_memory + 1, 10),
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
                    if dist > max_distance:
                        break
                    if (mem_id, rid) in existing_pairs:
                        continue

                    # Register nodes
                    if mem_id not in self.graph["nodes"]:
                        self.graph["nodes"][mem_id] = {
                            "collection": col_name, "added_at": now_str,
                        }
                        sqlite_nodes.append((mem_id, col_name, now_str, 0))
                    if rid not in self.graph["nodes"]:
                        self.graph["nodes"][rid] = {
                            "collection": col_name, "added_at": now_str,
                        }
                        sqlite_nodes.append((rid, col_name, now_str, 0))
                    self.graph["edges"].append({
                        "from": mem_id, "to": rid,
                        "type": "intra_similar", "created_at": now_str,
                        "source_collection": col_name,
                        "target_collection": col_name,
                    })
                    sqlite_edges.append((
                        mem_id, rid, "intra_similar", now_str,
                        col_name, col_name, 1.0,
                    ))
                    existing_pairs.add((mem_id, rid))
                    existing_pairs.add((rid, mem_id))
                    links_added += 1
                    col_new += 1
                    new_edges += 1

                    if links_added >= max_links_per_memory:
                        break

            if verbose:
                print(f"  {col_name}: {len(ids)} memories, {col_new} new intra-edges")

        # Single save at end
        if new_edges > 0:
            self._save_graph()
            # Dual-write batch to SQLite
            if self._sqlite_store is not None:
                try:
                    if sqlite_nodes:
                        self._sqlite_store.bulk_add_nodes(sqlite_nodes)
                    if sqlite_edges:
                        self._sqlite_store.bulk_add_edges(sqlite_edges)
                except Exception as exc:
                    _log.warning("SQLite dual-write failed for bulk_intra_link: %s", exc)

        return {
            "new_edges": new_edges,
            "collections_processed": collections_processed,
            "total_edges": len(self.graph.get("edges", [])),
        }

    def decay_edges(self, half_life_days=30, min_weight=0.05, prune_below=0.02,
                    decay_types=None, dry_run=False):
        """Apply age-based exponential decay to edge weights and prune weak edges.

        Edges without an explicit weight get an initial weight of 1.0.
        Weight decays as: w * 2^(-age_days / half_life_days).
        Edges below prune_below are removed.

        Args:
            half_life_days: Days for weight to halve (default 30).
            min_weight: Floor — weights below this still participate but are flagged.
            prune_below: Remove edges with decayed weight below this threshold.
            decay_types: Set of edge types to decay (default: hebbian_association only).
                         Pass None or empty to decay only hebbian_association.
            dry_run: If True, compute but don't modify the graph.

        Returns:
            dict: {decayed, pruned, total_before, total_after, avg_weight}
        """
        if decay_types is None:
            decay_types = {"hebbian_association"}

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

            # Parse creation time
            created_str = edge.get("created_at")
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    age_days = (now - created).total_seconds() / 86400.0
                except (ValueError, TypeError):
                    age_days = 0.0
            else:
                age_days = 0.0

            # Current weight (default 1.0 for legacy edges without weight)
            current_weight = edge.get("weight", 1.0)

            # Exponential decay: w * 2^(-age/half_life)
            decay_factor = math.pow(2, -age_days / half_life_days)
            new_weight = current_weight * decay_factor

            if new_weight < prune_below:
                pruned_count += 1
                if not dry_run:
                    continue  # skip — don't add to keep
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

            # Dual-decay in SQLite
            if self._sqlite_store is not None:
                try:
                    self._sqlite_store.decay_edges(
                        half_life_days=half_life_days,
                        prune_below=prune_below,
                        decay_types=decay_types,
                        dry_run=False,
                    )
                except Exception as exc:
                    _log.warning("SQLite dual-decay failed: %s", exc)

        avg_weight = sum(weights_after) / len(weights_after) if weights_after else 0.0

        return {
            "decayed": decayed_count,
            "pruned": pruned_count,
            "total_before": total_before,
            "total_after": len(keep),
            "avg_weight": round(avg_weight, 4),
        }

    # ------------------------------------------------------------------
    # Verification — compare JSON and SQLite for parity
    # ------------------------------------------------------------------

    def verify_graph_parity(self, sample_n=100):
        """Compare JSON and SQLite graph stores for parity.

        Checks:
          1. Node count match
          2. Edge count match (note: SQLite deduplicates via UNIQUE constraint,
             so it may have fewer edges if JSON has duplicates)
          3. Random sample of N edges from JSON verified to exist in SQLite

        Returns dict with counts, deltas, sample results, and overall parity_ok.
        """
        if self._sqlite_store is None:
            return {"error": "SQLite store not initialized (set CLARVIS_GRAPH_BACKEND=sqlite)"}

        json_nodes = len(self.graph.get("nodes", {}))
        json_edges = len(self.graph.get("edges", []))
        sqlite_nodes = self._sqlite_store.node_count()
        sqlite_edges = self._sqlite_store.edge_count()

        # Count JSON deduped edges (unique by from/to/type triple)
        json_edge_keys = set()
        json_duplicates = 0
        for e in self.graph.get("edges", []):
            key = (e["from"], e["to"], e.get("type"))
            if key in json_edge_keys:
                json_duplicates += 1
            json_edge_keys.add(key)
        json_unique_edges = len(json_edge_keys)

        # Random sample verification
        edges = self.graph.get("edges", [])
        sample_size = min(sample_n, len(edges))
        sample = random.sample(edges, sample_size) if sample_size > 0 else []

        matched = 0
        mismatched = []
        for edge in sample:
            sqlite_hits = self._sqlite_store.get_edges(
                from_id=edge["from"],
                to_id=edge["to"],
                edge_type=edge["type"],
            )
            if sqlite_hits:
                matched += 1
            else:
                mismatched.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "type": edge["type"],
                })

        # Edge type distribution comparison
        json_type_dist = {}
        for e in self.graph.get("edges", []):
            t = e.get("type", "unknown")
            json_type_dist[t] = json_type_dist.get(t, 0) + 1

        sqlite_stats = self._sqlite_store.stats()
        sqlite_type_dist = sqlite_stats.get("edge_types", {})

        # Parity is OK when:
        # - node counts match
        # - SQLite edges == JSON unique edges (dedup-adjusted)
        # - all sampled edges found in SQLite
        parity_ok = (
            json_nodes == sqlite_nodes
            and json_unique_edges == sqlite_edges
            and len(mismatched) == 0
        )

        return {
            "json_nodes": json_nodes,
            "sqlite_nodes": sqlite_nodes,
            "node_delta": sqlite_nodes - json_nodes,
            "json_edges": json_edges,
            "json_unique_edges": json_unique_edges,
            "json_duplicates": json_duplicates,
            "sqlite_edges": sqlite_edges,
            "edge_delta": sqlite_edges - json_unique_edges,
            "sample_size": sample_size,
            "sample_matched": matched,
            "sample_mismatched": len(mismatched),
            "mismatched_edges": mismatched[:10],
            "json_edge_types": json_type_dist,
            "sqlite_edge_types": sqlite_type_dist,
            "parity_ok": parity_ok,
        }
