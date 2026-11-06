# Runbook

## Daily checks

1. Run `python -m ch14.alerts normal` and read every line.
2. Once a week, run `python -m ch21.adoption` and compare it with
   the [pilot readout](../pilot.json).

## When something breaks

Page the platform on-call lead (see [Contacts](contacts.md)). If
answers go wrong after a change, follow [Rollback](rollback.md).

## Kill switch

The returns desk lead may stop the agent at any hour. Tickets go
back to the desk queue, and nothing is lost.
