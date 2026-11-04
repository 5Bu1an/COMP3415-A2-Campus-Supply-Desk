# CR-01 Express Delivery: Prediction (written before implementation)

Baseline for this change: commit eee5e8a (after Refactoring 3), 48 tests, 3 known defect failures.

## 1. Behaviour / requirements that will change
- Fulfillment accepts a third value, `express`, in the service API, CLI, and menu.
- New pricing rule: express always costs 1,200 cents and is never waived.
  The free-delivery threshold (>= 10,000 after discount) applies only to standard `delivery`.
- The invalid-fulfillment error message must now mention express.
- Unchanged: student discount (still on merchandise only, same rounding), pickup = free,
  standard delivery = 600 / free at 10,000, defaults regular + pickup, validation, stock,
  order numbering, history, cancellation.

## 2. Files / classes / methods I expect to modify
- `supplydesk/rules.py`: add `EXPRESS = "express"`, `EXPRESS_FEE_CENTS = 1200`, add EXPRESS to
  `FULFILLMENT_OPTIONS`.
- `supplydesk/service.py` -> `OrderService._price_request()`: add an express branch to the
  delivery-fee calculation; update the fulfillment error message. Because of Refactoring 1,
  I expect this to be the ONLY place pricing changes; quote() and place_order() need no edits.
- `supplydesk/cli.py`: I expect NO code change for `--fulfillment`, because Refactoring 2 made it
  use `FULFILLMENT_OPTIONS`; argparse help should list express automatically. May add help text.
- `supplydesk/menu.py` -> `read_request()`: update the hard-coded prompt text to include express.
- `FUNCTIONAL_SPEC.md` and `README.md`: document express.

## 3. Tests needed
- New file `tests/test_cr01_express.py`:
  - the 3 client examples (regular 2 notebooks = 2200; student 2 hoodies = 8400;
    regular 3 hoodies express = 13200 vs standard delivery 12000)
  - express fee is not waived at/above 10,000
  - quote and placed express order have identical pricing
  - express order keeps fulfillment/items/fee/discount/total after get_order, reopening, and cancel
  - an unknown value (e.g. "rush") is still rejected
  - CLI `quote --fulfillment express` returns total_cents 8400 and exit code 0
  - menu accepts `express` at the fulfillment prompt
- All 48 existing tests should still pass except the same 3 known defects (regression check).
  I do not expect to change any existing test.