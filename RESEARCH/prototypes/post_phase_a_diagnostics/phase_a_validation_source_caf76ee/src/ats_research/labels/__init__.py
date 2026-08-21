"""Outcome-only label namespace. Feature modules must never import this package."""

from ats_research.labels.forward_returns import LabelDefinition, compute_forward_returns, label_definitions

__all__ = ["LabelDefinition", "compute_forward_returns", "label_definitions"]

