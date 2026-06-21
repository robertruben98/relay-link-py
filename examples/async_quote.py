"""Async usage: fetch a quote and poll its execution status to completion.

Run with:  python examples/async_quote.py
"""

from __future__ import annotations

import asyncio

from relay_link import AsyncRelayClient, TradeType

NATIVE = "0x0000000000000000000000000000000000000000"


async def main() -> None:
    async with AsyncRelayClient() as client:
        quote = await client.get_quote(
            user="0x03508bb71268bba25ecacc8f620e01866650532c",
            origin_chain_id=8453,
            destination_chain_id=10,
            origin_currency=NATIVE,
            destination_currency=NATIVE,
            amount="1000000000000000000",
            trade_type=TradeType.EXACT_INPUT,
        )
        print(f"Got quote with {len(quote.steps)} steps")

        # After you submit the on-chain transaction from a step, take its
        # requestId and poll the status until it reaches a terminal state:
        #
        # request_id = quote.steps[0].request_id
        # status = await client.poll_status(request_id=request_id)
        # print(status.status)


if __name__ == "__main__":
    asyncio.run(main())
