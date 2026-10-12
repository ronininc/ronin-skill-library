# AfterShip Package Tracking

Track shipments through Hatch's managed AfterShip connector. Package tracking for store orders and fulfillment.

## When to use
Tracking a package, checking delivery status, registering new tracking numbers for store orders. Ties into the auto-fulfillment flow — every shipped order gets tracked here.

## Commands
Run via `muse.exec`:
- `aftership status` — check connector availability
- `aftership status --verify` — lightweight AfterShip probe
- `aftership detect-courier <tracking_number>` — detect possible couriers
- `aftership tracking <tracking_number>` — read tracking record
- `aftership register <tracking_number>` — register with AfterShip

## Rules
- Read-only by default. Registering new tracking numbers is fine for fulfillment.
- Part of the store auto-fulfillment pipeline — tracking numbers flow from fulfillment to AfterShip automatically.
