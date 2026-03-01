#!/usr/bin/env python3
"""
OpenCog Hyperon AtomSpace — Typed Hypergraph Knowledge Representation

Implements core AtomSpace concepts adapted for Clarvis:

1. Atoms — Nodes (concepts) and Links (typed relationships between atoms)
2. Types — Hierarchical type system (ConceptNode, PredicateNode, EvaluationLink, etc.)
3. Attention Values (STI/LTI) — Short-term / long-term importance (ECAN)
4. Truth Values — Strength + confidence for probabilistic reasoning
5. Pattern Matching — Find subgraph patterns in the atomspace
6. Inference — Simple forward chaining on EvaluationLinks

Key difference from brain.py's flat graph:
  - brain.py graph: node_id -> [{target, type, weight}] (flat edges)
  - AtomSpace: typed hypergraph where links connect N atoms, links can
    contain links (higher-order), and every atom has attention + truth values

References:
  - Goertzel et al. (2014) "OpenCog: A Software Framework for Integrative AGI"
  - Goertzel (2021) "Hyperon: A Framework for AGI at Scale"
  - ECAN (Economic Attention Networks) — Goertzel et al.

Integration points:
  - brain.py: AtomSpace overlays brain's graph with typed semantics
  - episodic_memory.py: Episodes become ContextLinks in the atomspace
  - soar_engine.py: Goals become GoalNodes, operators become SchemaNodes
  - attention.py: STI maps to GWT salience

Usage:
    from hyperon_atomspace import atomspace
    # Add concepts
    n1 = atomspace.add_node("ConceptNode", "episodic_memory")
    n2 = atomspace.add_node("ConceptNode", "retrieval_accuracy")
    # Link them
    atomspace.add_link("EvaluationLink", [n1, n2],
                       tv={"strength": 0.85, "confidence": 0.9})
    # Pattern match
    results = atomspace.pattern_match("EvaluationLink", [("ConceptNode", "episodic_memory"), None])
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path("/home/agent/.openclaw/workspace/data/atomspace")
DATA_DIR.mkdir(parents=True, exist_ok=True)
ATOMS_FILE = DATA_DIR / "atoms.json"
STATS_FILE = DATA_DIR / "stats.json"

# ------------------------------------------------------------------
# Type hierarchy (simplified OpenCog types)
# ------------------------------------------------------------------
NODE_TYPES = {
    "ConceptNode":    "General concept or category",
    "PredicateNode":  "A predicate (property or relation name)",
    "SchemaNode":     "An executable procedure or operator",
    "GoalNode":       "A goal or desired state",
    "NumberNode":     "A numeric value",
    "ContextNode":    "An episodic or situational context",
    "VariableNode":   "A pattern-matching variable (wildcard)",
}

LINK_TYPES = {
    "EvaluationLink":   "Predicate applied to arguments: (Pred, arg1, arg2, ...)",
    "InheritanceLink":  "A is-a B (taxonomic)",
    "SimilarityLink":   "A is similar to B (symmetric)",
    "ImplicationLink":  "A implies B (causal/logical)",
    "ContextLink":      "A occurs in context B",
    "ExecutionLink":    "Schema applied with inputs/outputs",
    "MemberLink":       "A is member of set B",
    "ListLink":         "Ordered list of atoms",
    "BindLink":         "Pattern + rewrite rule for inference",
    "StateLink":        "Current state of a stateful atom",
}

ALL_TYPES = {**NODE_TYPES, **LINK_TYPES}


class TruthValue:
    """OpenCog-style truth value: (strength, confidence).

    strength: probability / degree of truth [0, 1]
    confidence: how much evidence supports this [0, 1]
      confidence = n / (n + k) where n = evidence count, k = lookahead (default 200)
    """

    def __init__(self, strength=1.0, confidence=0.0):
        self.strength = max(0.0, min(1.0, strength))
        self.confidence = max(0.0, min(1.0, confidence))

    def merge(self, other):
        """Merge two truth values (revision rule: weighted by confidence)."""
        total_conf = self.confidence + other.confidence
        if total_conf < 1e-9:
            return TruthValue(0.5, 0.0)
        new_strength = (
            self.strength * self.confidence + other.strength * other.confidence
        ) / total_conf
        # Confidence increases with more evidence (but never exceeds 1)
        new_confidence = min(1.0, total_conf / (total_conf + 0.5))
        return TruthValue(new_strength, new_confidence)

    def to_dict(self):
        return {"strength": round(self.strength, 4),
                "confidence": round(self.confidence, 4)}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("strength", 1.0), d.get("confidence", 0.0))

    def __repr__(self):
        return f"TV({self.strength:.2f}, {self.confidence:.2f})"


class AttentionValue:
    """ECAN Attention Value: (STI, LTI).

    STI (Short-Term Importance): volatile, decays quickly. Maps to GWT salience.
    LTI (Long-Term Importance): stable, decays slowly. Maps to memory importance.
    """

    def __init__(self, sti=0.0, lti=0.0):
        self.sti = sti
        self.lti = lti

    def to_dict(self):
        return {"sti": round(self.sti, 3), "lti": round(self.lti, 3)}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("sti", 0.0), d.get("lti", 0.0))


class Atom:
    """Base atom — either a Node or a Link."""

    def __init__(self, atom_type, name=None, outgoing=None, tv=None, av=None,
                 atom_id=None):
        self.id = atom_id or f"atom_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        self.type = atom_type
        self.name = name  # For nodes; None for links
        self.outgoing = outgoing or []  # List of atom IDs (for links)
        self.tv = tv or TruthValue()
        self.av = av or AttentionValue()
        self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_node(self):
        return self.type in NODE_TYPES

    @property
    def is_link(self):
        return self.type in LINK_TYPES

    def to_dict(self):
        d = {
            "id": self.id,
            "type": self.type,
            "tv": self.tv.to_dict(),
            "av": self.av.to_dict(),
            "created_at": self.created_at,
        }
        if self.name is not None:
            d["name"] = self.name
        if self.outgoing:
            d["outgoing"] = self.outgoing
        return d

    @classmethod
    def from_dict(cls, d):
        a = cls(
            atom_type=d["type"],
            name=d.get("name"),
            outgoing=d.get("outgoing", []),
            tv=TruthValue.from_dict(d.get("tv", {})),
            av=AttentionValue.from_dict(d.get("av", {})),
            atom_id=d["id"],
        )
        a.created_at = d.get("created_at", a.created_at)
        return a

    def __repr__(self):
        if self.is_node:
            return f"{self.type}(\"{self.name}\") {self.tv}"
        else:
            return f"{self.type}({self.outgoing}) {self.tv}"


class AtomSpace:
    """
    Typed hypergraph knowledge store.

    Atoms (nodes and links) form a typed hypergraph where:
    - Nodes represent concepts, predicates, schemas, goals
    - Links represent relationships between atoms (can be higher-order)
    - Every atom has a TruthValue (strength, confidence) and AttentionValue (STI, LTI)
    """

    def __init__(self):
        self.atoms = {}          # id -> Atom
        self._name_index = {}    # (type, name) -> atom_id  (for nodes)
        self._type_index = {}    # type -> set of atom_ids
        self._incoming = {}      # atom_id -> set of link_ids that reference it
        self._load()

    def _load(self):
        if ATOMS_FILE.exists():
            try:
                data = json.loads(ATOMS_FILE.read_text())
                for d in data.get("atoms", []):
                    atom = Atom.from_dict(d)
                    self.atoms[atom.id] = atom
                self._rebuild_indices()
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        data = {
            "atoms": [a.to_dict() for a in self.atoms.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(self.atoms),
        }
        ATOMS_FILE.write_text(json.dumps(data, indent=2))

    def _rebuild_indices(self):
        """Rebuild all lookup indices from atoms dict."""
        self._name_index.clear()
        self._type_index.clear()
        self._incoming.clear()
        for atom in self.atoms.values():
            if atom.name is not None:
                self._name_index[(atom.type, atom.name)] = atom.id
            self._type_index.setdefault(atom.type, set()).add(atom.id)
            for target_id in atom.outgoing:
                self._incoming.setdefault(target_id, set()).add(atom.id)

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def add_node(self, node_type, name, tv=None, av=None):
        """Add a node (or return existing if same type+name).

        Args:
            node_type: One of NODE_TYPES
            name: Node name string
            tv: Optional TruthValue dict {"strength": ..., "confidence": ...}
            av: Optional AttentionValue dict {"sti": ..., "lti": ...}

        Returns:
            atom_id string
        """
        # Check for existing
        key = (node_type, name)
        if key in self._name_index:
            existing_id = self._name_index[key]
            existing = self.atoms.get(existing_id)
            if existing:
                # Merge truth values if provided
                if tv:
                    new_tv = TruthValue.from_dict(tv)
                    existing.tv = existing.tv.merge(new_tv)
                if av:
                    existing.av = AttentionValue.from_dict(av)
                self._save()
                return existing_id

        tv_obj = TruthValue.from_dict(tv) if tv else TruthValue(1.0, 0.0)
        av_obj = AttentionValue.from_dict(av) if av else AttentionValue()

        atom = Atom(node_type, name=name, tv=tv_obj, av=av_obj)
        self.atoms[atom.id] = atom
        self._name_index[key] = atom.id
        self._type_index.setdefault(node_type, set()).add(atom.id)
        self._save()
        return atom.id

    def add_link(self, link_type, targets, tv=None, av=None):
        """Add a typed link between atoms.

        Args:
            link_type: One of LINK_TYPES
            targets: List of atom_ids (the outgoing set)
            tv: Optional TruthValue dict
            av: Optional AttentionValue dict

        Returns:
            atom_id of the link
        """
        # Validate targets exist
        valid_targets = [t for t in targets if t in self.atoms]
        if len(valid_targets) != len(targets):
            missing = set(targets) - set(valid_targets)
            print(f"Warning: {len(missing)} target atom(s) not found, skipping those",
                  file=sys.stderr)
            if not valid_targets:
                return None

        # Check for existing identical link
        for existing_id in self._type_index.get(link_type, set()):
            existing = self.atoms.get(existing_id)
            if existing and existing.outgoing == valid_targets:
                if tv:
                    new_tv = TruthValue.from_dict(tv)
                    existing.tv = existing.tv.merge(new_tv)
                self._save()
                return existing_id

        tv_obj = TruthValue.from_dict(tv) if tv else TruthValue(1.0, 0.5)
        av_obj = AttentionValue.from_dict(av) if av else AttentionValue()

        atom = Atom(link_type, outgoing=valid_targets, tv=tv_obj, av=av_obj)
        self.atoms[atom.id] = atom
        self._type_index.setdefault(link_type, set()).add(atom.id)
        for t in valid_targets:
            self._incoming.setdefault(t, set()).add(atom.id)
        self._save()
        return atom.id

    def get_atom(self, atom_id):
        """Get an atom by ID."""
        atom = self.atoms.get(atom_id)
        return atom.to_dict() if atom else None

    def get_node(self, node_type, name):
        """Get a node by type and name."""
        aid = self._name_index.get((node_type, name))
        if aid:
            atom = self.atoms.get(aid)
            return atom.to_dict() if atom else None
        return None

    def remove_atom(self, atom_id):
        """Remove an atom and all links referencing it."""
        atom = self.atoms.pop(atom_id, None)
        if not atom:
            return False

        # Remove from indices
        if atom.name is not None:
            self._name_index.pop((atom.type, atom.name), None)
        if atom.type in self._type_index:
            self._type_index[atom.type].discard(atom_id)

        # Remove links that reference this atom
        incoming = list(self._incoming.pop(atom_id, set()))
        for link_id in incoming:
            self.remove_atom(link_id)  # Recursive

        # Clean up outgoing references
        for target_id in atom.outgoing:
            if target_id in self._incoming:
                self._incoming[target_id].discard(atom_id)

        self._save()
        return True

    # ------------------------------------------------------------------
    # Pattern Matching
    # ------------------------------------------------------------------

    def pattern_match(self, link_type, pattern, max_results=20):
        """Find links matching a pattern.

        Pattern is a list where each element is either:
        - (type, name): match a specific node
        - None: wildcard (match any atom)
        - atom_id string: match a specific atom

        Returns:
            List of matching link dicts with their outgoing atoms resolved
        """
        candidates = self._type_index.get(link_type, set())
        results = []

        for link_id in candidates:
            link = self.atoms.get(link_id)
            if not link or len(link.outgoing) != len(pattern):
                continue

            match = True
            for i, p in enumerate(pattern):
                if p is None:
                    continue  # Wildcard
                target = self.atoms.get(link.outgoing[i])
                if not target:
                    match = False
                    break
                if isinstance(p, tuple):
                    # (type, name) match
                    if target.type != p[0] or target.name != p[1]:
                        match = False
                        break
                elif isinstance(p, str):
                    # atom_id match
                    if link.outgoing[i] != p:
                        match = False
                        break

            if match:
                resolved = link.to_dict()
                resolved["resolved_outgoing"] = [
                    self.atoms[aid].to_dict() if aid in self.atoms else {"id": aid}
                    for aid in link.outgoing
                ]
                results.append(resolved)
                if len(results) >= max_results:
                    break

        # Sort by truth value strength * confidence
        results.sort(
            key=lambda r: r["tv"]["strength"] * r["tv"]["confidence"],
            reverse=True,
        )
        return results

    def get_incoming(self, atom_id, link_type=None):
        """Get all links pointing to this atom.

        Args:
            atom_id: Target atom
            link_type: Optional filter by link type

        Returns:
            List of link dicts
        """
        link_ids = self._incoming.get(atom_id, set())
        results = []
        for lid in link_ids:
            link = self.atoms.get(lid)
            if link and (link_type is None or link.type == link_type):
                results.append(link.to_dict())
        return results

    def get_outgoing(self, link_id):
        """Get all atoms in a link's outgoing set."""
        link = self.atoms.get(link_id)
        if not link:
            return []
        return [self.atoms[aid].to_dict() for aid in link.outgoing
                if aid in self.atoms]

    # ------------------------------------------------------------------
    # Inference (Simple Forward Chaining)
    # ------------------------------------------------------------------

    def forward_chain(self, start_node_id, link_type="ImplicationLink", max_depth=3):
        """Simple forward chaining inference.

        Follow ImplicationLinks (A → B) from start node, propagating truth values.

        Returns:
            List of (depth, atom_dict, propagated_tv) tuples
        """
        visited = {start_node_id}
        frontier = [(start_node_id, 0, TruthValue(1.0, 1.0))]
        results = []

        while frontier:
            current_id, depth, current_tv = frontier.pop(0)
            if depth >= max_depth:
                continue

            # Find implication links where current is first outgoing
            for link_id in self._type_index.get(link_type, set()):
                link = self.atoms.get(link_id)
                if not link or len(link.outgoing) < 2:
                    continue
                if link.outgoing[0] != current_id:
                    continue

                target_id = link.outgoing[1]
                if target_id in visited:
                    continue
                visited.add(target_id)

                target = self.atoms.get(target_id)
                if not target:
                    continue

                # Propagate truth value: P(B) = P(B|A) * P(A)
                propagated = TruthValue(
                    strength=link.tv.strength * current_tv.strength,
                    confidence=min(link.tv.confidence, current_tv.confidence) * 0.9,
                )

                results.append((depth + 1, target.to_dict(), propagated.to_dict()))
                frontier.append((target_id, depth + 1, propagated))

        return results

    # ------------------------------------------------------------------
    # ECAN (Economic Attention Network) — simplified
    # ------------------------------------------------------------------

    def spread_attention(self, source_id, amount=10.0):
        """Spread STI from a source atom to its neighbors.

        ECAN: atoms that are attended spread importance to connected atoms.
        This maps to GWT broadcasting.
        """
        source = self.atoms.get(source_id)
        if not source:
            return

        # Tax the source
        source.av.sti = max(0.0, source.av.sti - amount * 0.1)

        # Find neighbors (incoming links + their outgoing sets)
        neighbors = set()
        for link_id in self._incoming.get(source_id, set()):
            link = self.atoms.get(link_id)
            if link:
                for target_id in link.outgoing:
                    if target_id != source_id:
                        neighbors.add(target_id)

        # Also check outgoing from links where source is part of
        for link_id in self._type_index.get("EvaluationLink", set()):
            link = self.atoms.get(link_id)
            if link and source_id in link.outgoing:
                for target_id in link.outgoing:
                    if target_id != source_id:
                        neighbors.add(target_id)

        if not neighbors:
            return

        per_neighbor = amount / len(neighbors)
        for nid in neighbors:
            neighbor = self.atoms.get(nid)
            if neighbor:
                neighbor.av.sti += per_neighbor

        self._save()

    def decay_attention(self, decay_rate=0.95):
        """Decay all STI values (simulates forgetting / attention fading)."""
        for atom in self.atoms.values():
            atom.av.sti *= decay_rate
            # STI below threshold becomes 0
            if abs(atom.av.sti) < 0.01:
                atom.av.sti = 0.0
        self._save()

    def attentional_focus(self, n=10):
        """Get the top-N atoms by STI (the 'attentional focus' in ECAN).

        Returns:
            List of atom dicts sorted by STI (highest first)
        """
        ranked = sorted(self.atoms.values(), key=lambda a: a.av.sti, reverse=True)
        return [a.to_dict() for a in ranked[:n] if a.av.sti > 0]

    # ------------------------------------------------------------------
    # Bridge to Brain.py Graph
    # ------------------------------------------------------------------

    def import_from_brain_graph(self, limit=200):
        """Import nodes and edges from brain.py's relationship graph.

        Converts flat graph edges into typed AtomSpace links.
        """
        try:
            from brain import brain
        except ImportError:
            return {"error": "brain not available"}

        imported_nodes = 0
        imported_links = 0

        # Import graph nodes
        nodes = brain.graph.get("nodes", {})
        if isinstance(nodes, dict):
            node_ids = list(nodes.keys())[:limit]
        elif isinstance(nodes, list):
            node_ids = [n if isinstance(n, str) else n.get("id", "") for n in nodes[:limit]]
        else:
            node_ids = []
        for node_id in node_ids:
            if node_id:
                self.add_node("ConceptNode", node_id,
                              tv={"strength": 0.8, "confidence": 0.3})
                imported_nodes += 1

        # Import graph edges (brain graph stores edges as a flat list)
        edges = brain.graph.get("edges", [])
        if isinstance(edges, list):
            edge_list = edges[:limit]
        elif isinstance(edges, dict):
            edge_list = []
            for source_id, elist in list(edges.items())[:limit]:
                for e in (elist if isinstance(elist, list) else [elist]):
                    e["from"] = source_id
                    edge_list.append(e)
        else:
            edge_list = []

        for edge in edge_list:
            source_id = edge.get("from", "")
            target_id = edge.get("to", edge.get("target", ""))
            if not source_id or not target_id:
                continue

            # Ensure both nodes exist
            src_atom = self._name_index.get(("ConceptNode", source_id))
            if not src_atom:
                src_atom = self.add_node("ConceptNode", source_id,
                                         tv={"strength": 0.7, "confidence": 0.2})
                imported_nodes += 1
            tgt_atom = self._name_index.get(("ConceptNode", target_id))
            if not tgt_atom:
                tgt_atom = self.add_node("ConceptNode", target_id,
                                         tv={"strength": 0.7, "confidence": 0.2})
                imported_nodes += 1

            edge_type = edge.get("type", "similar_to")
            link_type = {
                "similar_to": "SimilarityLink",
                "cross_collection": "ContextLink",
                "caused": "ImplicationLink",
                "enabled": "ImplicationLink",
                "fixed": "ImplicationLink",
            }.get(edge_type, "SimilarityLink")

            weight = edge.get("weight", 0.5)
            self.add_link(link_type, [src_atom, tgt_atom],
                          tv={"strength": weight, "confidence": 0.4})
            imported_links += 1

        return {"imported_nodes": imported_nodes, "imported_links": imported_links}

    # ------------------------------------------------------------------
    # Convenience: SOAR integration
    # ------------------------------------------------------------------

    def register_goal(self, goal_name, goal_id):
        """Register a SOAR goal as a GoalNode."""
        return self.add_node("GoalNode", goal_name,
                             tv={"strength": 1.0, "confidence": 0.8},
                             av={"sti": 5.0, "lti": 3.0})

    def register_operator(self, op_name, goal_atom_id, preference=0.5):
        """Register a SOAR operator as a SchemaNode linked to a goal."""
        schema_id = self.add_node("SchemaNode", op_name,
                                  tv={"strength": preference, "confidence": 0.5})
        self.add_link("ExecutionLink", [schema_id, goal_atom_id],
                      tv={"strength": preference, "confidence": 0.5})
        return schema_id

    # ------------------------------------------------------------------
    # Stats & Maintenance
    # ------------------------------------------------------------------

    def stats(self):
        """Get atomspace statistics."""
        type_counts = {}
        for atom in self.atoms.values():
            type_counts[atom.type] = type_counts.get(atom.type, 0) + 1

        nodes = sum(1 for a in self.atoms.values() if a.is_node)
        links = sum(1 for a in self.atoms.values() if a.is_link)

        avg_strength = 0.0
        avg_confidence = 0.0
        if self.atoms:
            avg_strength = sum(a.tv.strength for a in self.atoms.values()) / len(self.atoms)
            avg_confidence = sum(a.tv.confidence for a in self.atoms.values()) / len(self.atoms)

        focus = self.attentional_focus(5)

        return {
            "total_atoms": len(self.atoms),
            "nodes": nodes,
            "links": links,
            "type_counts": type_counts,
            "avg_truth_strength": round(avg_strength, 3),
            "avg_truth_confidence": round(avg_confidence, 3),
            "attentional_focus": [f"{a['type']}({a.get('name', a.get('outgoing', '?'))})" for a in focus],
        }

    def prune(self, min_lti=0.0, min_confidence=0.0):
        """Remove atoms with low long-term importance and confidence."""
        to_remove = []
        for atom in self.atoms.values():
            if atom.av.lti <= min_lti and atom.tv.confidence <= min_confidence:
                to_remove.append(atom.id)
        for aid in to_remove:
            self.remove_atom(aid)
        return len(to_remove)

    def save(self):
        """Public save."""
        self._save()


# Singleton
_atomspace = None

def get_atomspace():
    global _atomspace
    if _atomspace is None:
        _atomspace = AtomSpace()
    return _atomspace

atomspace = get_atomspace()


# === CLI ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: hyperon_atomspace.py <command> [args]")
        print("Commands:")
        print("  node <type> <name> [str] [conf]     - Add a node")
        print("  link <type> <id1> <id2> [str] [conf] - Add a link")
        print("  get <atom_id>                        - Get an atom")
        print("  find <type> <name>                   - Find a node")
        print("  match <link_type> <pat1> <pat2>      - Pattern match")
        print("  chain <start_id> [depth]             - Forward chain inference")
        print("  focus [n]                            - Attentional focus")
        print("  import-brain [limit]                 - Import from brain graph")
        print("  stats                                - Show statistics")
        print("  prune                                - Remove low-value atoms")
        sys.exit(0)

    cmd = sys.argv[1]
    a = get_atomspace()

    if cmd == "node":
        ntype = sys.argv[2] if len(sys.argv) > 2 else "ConceptNode"
        name = sys.argv[3] if len(sys.argv) > 3 else "unnamed"
        strength = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
        confidence = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
        aid = a.add_node(ntype, name, tv={"strength": strength, "confidence": confidence})
        print(f"Added: {aid} — {ntype}(\"{name}\") TV({strength}, {confidence})")

    elif cmd == "link":
        ltype = sys.argv[2] if len(sys.argv) > 2 else "EvaluationLink"
        id1 = sys.argv[3] if len(sys.argv) > 3 else ""
        id2 = sys.argv[4] if len(sys.argv) > 4 else ""
        strength = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
        confidence = float(sys.argv[6]) if len(sys.argv) > 6 else 0.5
        lid = a.add_link(ltype, [id1, id2],
                         tv={"strength": strength, "confidence": confidence})
        if lid:
            print(f"Added: {lid} — {ltype}([{id1}, {id2}]) TV({strength}, {confidence})")
        else:
            print("Failed to add link (missing targets?)")

    elif cmd == "get":
        aid = sys.argv[2] if len(sys.argv) > 2 else ""
        atom = a.get_atom(aid)
        if atom:
            print(json.dumps(atom, indent=2))
        else:
            print(f"Atom {aid} not found")

    elif cmd == "find":
        ntype = sys.argv[2] if len(sys.argv) > 2 else "ConceptNode"
        name = sys.argv[3] if len(sys.argv) > 3 else ""
        atom = a.get_node(ntype, name)
        if atom:
            print(json.dumps(atom, indent=2))
        else:
            print(f"No {ntype} named '{name}'")

    elif cmd == "match":
        ltype = sys.argv[2] if len(sys.argv) > 2 else "EvaluationLink"
        # Parse pattern: "ConceptNode:name" or "None" for wildcard
        pattern = []
        for p in sys.argv[3:]:
            if p.lower() == "none" or p == "*":
                pattern.append(None)
            elif ":" in p:
                parts = p.split(":", 1)
                pattern.append((parts[0], parts[1]))
            else:
                pattern.append(p)  # atom_id

        results = a.pattern_match(ltype, pattern)
        if not results:
            print("No matches found")
        else:
            for r in results:
                resolved = r.get("resolved_outgoing", [])
                atoms_str = ", ".join(
                    f"{ra.get('type', '?')}({ra.get('name', ra.get('id', '?')[:20])})"
                    for ra in resolved
                )
                print(f"  {r['type']}({atoms_str}) "
                      f"TV({r['tv']['strength']:.2f}, {r['tv']['confidence']:.2f})")

    elif cmd == "chain":
        start = sys.argv[2] if len(sys.argv) > 2 else ""
        depth = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        results = a.forward_chain(start, max_depth=depth)
        if not results:
            print("No inference results")
        else:
            for d, atom, tv in results:
                indent = "  " * d
                name = atom.get("name", atom.get("id", "?")[:20])
                print(f"  {indent}depth={d}: {atom['type']}(\"{name}\") "
                      f"TV({tv['strength']:.3f}, {tv['confidence']:.3f})")

    elif cmd == "focus":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        focus = a.attentional_focus(n)
        if not focus:
            print("Attentional focus is empty")
        else:
            print(f"Attentional Focus ({len(focus)} atoms):")
            for atom in focus:
                name = atom.get("name", str(atom.get("outgoing", "?")))
                print(f"  STI={atom['av']['sti']:.1f}  {atom['type']}(\"{name}\") "
                      f"TV({atom['tv']['strength']:.2f})")

    elif cmd == "import-brain":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        result = a.import_from_brain_graph(limit)
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        print(json.dumps(a.stats(), indent=2))

    elif cmd == "prune":
        removed = a.prune()
        print(f"Pruned {removed} atoms")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
