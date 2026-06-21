"""Get a cross-chain quote: bridge 1 ETH from Base (8453) to Optimism (10).

Run with:  python examples/quote.py
"""

from __future__ import annotations

from relay_link import RelayClient, TradeType

NATIVE = "0x0000000000000000000000000000000000000000"


def main() -> None:
    with RelayClient() as client:
        quote = client.get_quote(
            user="0x03508bb71268bba25ecacc8f620e01866650532c",
            origin_chain_id=8453,
            destination_chain_id=10,
            origin_currency=NATIVE,
            destination_currency=NATIVE,
            amount="1000000000000000000",  # 1 ETH, in wei
            trade_type=TradeType.EXACT_INPUT,
        )

    print(f"Steps to execute: {len(quote.steps)}")
    for step in quote.steps:
        print(f"  - [{step.kind}] {step.id}: {step.action}")
    if quote.fees and quote.fees.gas:
        print(f"Origin gas fee: {quote.fees.gas.amount_usd} USD")


if __name__ == "__main__":
    main()
