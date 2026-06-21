"""Live integration test. Deselected by default (``-m 'not integration'``).

Run explicitly with: ``pytest -m integration``
"""

from __future__ import annotations

import pytest

from relay_link import RelayClient


@pytest.mark.integration
def test_live_get_chains() -> None:
    """Hit the real, keyless GET /chains endpoint and parse the response."""
    with RelayClient() as client:
        chains = client.get_chains()
    assert len(chains) > 0
    assert all(isinstance(c.id, int) for c in chains)
    # Ethereum mainnet should always be present.
    assert any(c.id == 1 for c in chains)
