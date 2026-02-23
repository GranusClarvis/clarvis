"""
ClarvisConsciousness — Consciousness stack: IIT Phi, GWT spotlight, self-model.

Components:
- AttentionSpotlight (GWT): capacity-limited broadcast of salient items
- compute_phi (IIT): integrated information metric across memory partitions
- SelfModel: meta-cognitive capability tracking and awareness levels
- CapabilityAssessor: scored capability assessment framework

Usage:
    from clarvis_consciousness import AttentionSpotlight, compute_phi, SelfModel

    spotlight = AttentionSpotlight(capacity=7)
    spotlight.submit("user question", source="conversation", importance=0.9)
    focus = spotlight.focus()

    phi = compute_phi(nodes, edges)

    model = SelfModel()
    model.think_about_thinking("Am I improving?")
"""

from clarvis_consciousness.gwt import AttentionSpotlight
from clarvis_consciousness.phi import compute_phi, PhiConfig
from clarvis_consciousness.self_model import SelfModel, CapabilityAssessor

__version__ = "1.0.0"
__all__ = [
    "AttentionSpotlight",
    "compute_phi",
    "PhiConfig",
    "SelfModel",
    "CapabilityAssessor",
]
