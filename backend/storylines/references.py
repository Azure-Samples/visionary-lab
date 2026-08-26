"""Owner-scoped durable reference helpers for storyline uploads."""

from __future__ import annotations

import hashlib


def storyline_reference_prefix(owner_id: str) -> str:
    """Return a non-reversible Blob prefix dedicated to one storyline owner."""

    owner_scope = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:24]
    return f"storyline-references/{owner_scope}/"


def is_owned_storyline_reference(blob_name: str, owner_id: str) -> bool:
    return blob_name.startswith(storyline_reference_prefix(owner_id))
