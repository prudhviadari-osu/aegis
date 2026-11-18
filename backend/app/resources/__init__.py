"""Resource safety layer (Milestone 3.5): protect the user's hardware by backing
off before Aegis adds to the sustained-heat / high-load conditions that age a
battery."""
from .monitor import read_state, ResourceState
from .governor import Governor, Decision

__all__ = ["read_state", "ResourceState", "Governor", "Decision"]
