# Etsy

Manage Robbie's Etsy shop through Open API v3. Listings, inventory, orders, and receipts.

## When to use
Anything involving the Etsy shop: checking orders, managing listings, updating inventory, pulling receipts. Etsy is the eBay replacement — this is where marketplace selling happens now.

## Commands
Run via `muse.exec`:
- `etsy-cli status` — check if connected
- `etsy-cli me` — authenticated user info
- `etsy-cli shop <shop_id>` — shop details
- `etsy-cli listings --shop-id <id> --state active` — active listings
- `etsy-cli listing <listing_id>` — single listing details
- `etsy-cli inventory <listing_id>` — inventory for a listing
- `etsy-cli receipts --shop-id <id>` — orders/receipts
- `etsy-cli request <method> <path>` — advanced API calls

## Rules
- Read-only by default. Don't create, update, or delete listings without Robbie's explicit tap.
- Order fulfillment goes through the store auto-fulfillment flow, not manual Etsy actions.
