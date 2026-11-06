# Alerts

The rules live in [alerts.py](../../ch14/alert.py). Replay a normal
day with `python -m ch14.alerts normal`.

## Alert list

| Alert | Fires when | Severity |
|---|---|---|
| error rate | errors over 5% of conversations | page |
| slow replies | 95th percentile reply over 8 seconds | page |
| token drift | tokens 1.5 times the normal day | ticket |
| handoff drift | handoffs 2.5 times the normal day | ticket |

## Who is paged

A page goes to the platform on-call (L2) at any hour. A ticket goes
to the returns desk lead's queue for the next working day. Each alert
links to its step in the [runbook](runbook.md).
