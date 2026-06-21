"""List the chains supported by Relay (no API key required).

Run with:  python examples/list_chains.py
"""

from __future__ import annotations

from relay_link import RelayClient


def main() -> None:
    with RelayClient() as client:
        chains = client.get_chains()

    print(f"{len(chains)} supported chains:")
    for chain in chains:
        flag = "" if chain.deposit_enabled else "  (deposits disabled)"
        print(f"  {chain.id:>8}  {chain.display_name or chain.name}{flag}")


if __name__ == "__main__":
    main()
