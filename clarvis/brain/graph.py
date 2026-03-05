"""Brain graph operations — relationship storage, traversal, backfill, decay."""

import json
import logging
import math
import os
import fcntl
from datetime import datetime, timezone

_log = logging.getLogger("clarvis.brain.graph")

from .constants import MEMORIES, GOALS, PROCEDURES, DEFAULT_COLLECTIONS


class GraphMixin:
    """Graph operations for ClarvisBrain (mixed into the main class)."""

    def _load_graph(self):
        """Load relationship graph with corruption recovery + file locking + integrity check."""
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
                return
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
                        return
                except Exception:
                    pass
        self.graph = {"nodes": {}, "edges": []}

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
        """Add a relationship between two memories."""
        if from_id not in self.graph["nodes"]:
            self.graph["nodes"][from_id] = {
                "collection": source_collection or self._infer_collection(from_id),
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
        if to_id not in self.graph["nodes"]:
            self.graph["nodes"][to_id] = {
                "collection": target_collection or self._infer_collection(to_id),
                "added_at": datetime.now(timezone.utc).isoformat(),
            }

        edge = {
            "from": from_id,
            "to": to_id,
            "type": relationship_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
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
        """Get memories related to a given memory"""
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
        for edge in self.graph.get("edges", []):
            for key in ("from", "to"):
                node_id = edge.get(key)
                if node_id and node_id not in self.graph["nodes"]:
                    collection = edge.get(f"{'source' if key == 'from' else 'target'}_collection")
                    self.graph["nodes"][node_id] = {
                        "collection": collection or self._infer_collection(node_id),
                        "added_at": datetime.now(timezone.utc).isoformat(),
                        "backfilled": True,
                    }
                    backfilled += 1
        if backfilled > 0:
            self._save_graph()
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

        avg_weight = sum(weights_after) / len(weights_after) if weights_after else 0.0

        return {
            "decayed": decayed_count,
            "pruned": pruned_count,
            "total_before": total_before,
            "total_after": len(keep),
            "avg_weight": round(avg_weight, 4),
        }
