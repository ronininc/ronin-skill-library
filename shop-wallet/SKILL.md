# Shop Wallet

Shopify Shop wallet CLI wrapper. Store checkout and wallet operations.

## When to use
Anything involving the Shop wallet for the Ronin store — checking wallet status, processing wallet payments, store checkout flows.

## Commands
Run via `muse.exec`:
- `shop-wallet-cli --help` — see available operations
- Pass through Shopify Shop arguments as needed

## Rules
- Tied to the Ronin store checkout. Don't process payments without going through the store's fulfillment flow.
- Read-only checks are fine anytime.
