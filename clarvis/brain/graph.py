"""Brain graph operations — relationship storage, traversal, backfill."""

import json
import os
import fcntl
from datetime import datetime, timezone

from .constants import MEMORIES, GOALS, PROCEDURES, DEFAULT_COLLECTIONS


class GraphMixin:
    """Graph operations for ClarvisBrain (mixed into the main class)."""

    def _load_graph(self):
        """Load relationship graph with corruption recovery + file locking"""
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    self.graph = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return
            except (json.JSONDecodeError, IOError, OSError):
                broken_path = self.graph_file + ".broken"
                os.rename(self.graph_file, broken_path)
                try:
                    with open(broken_path, 'r') as f:
                        raw = f.read()
                    last_brace = raw.rfind('},')
                    if last_brace > 0:
                        valid = raw[:last_brace+1] + '\n  ]\n}'
                        self.graph = json.loads(valid)
                        self._save_graph()
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
