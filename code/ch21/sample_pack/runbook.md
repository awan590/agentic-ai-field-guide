# Runbook: returns agent

The agent drafts a reply for every returns ticket, and a person on the
desk sends it. A person still approves every refund.

## Daily checks

1. Read the alerts from the last 24 hours ([alerts](alerts.md)).
2. Run the adoption report: `python -m ch21.adoption`.
3. Before any change goes live, run the [eval gate](evals.md).

## When something breaks

1. The person who sees it first tells the returns desk lead (L1).
2. If a shopper got a wrong answer, the desk lead pulls the kill
   switch below, then calls the platform on-call (L2, see
   [contacts](contacts.md)).
3. If a new version caused it, roll back with
   `python -m ch16.rollback`. If not, the switch stays pulled until
   the cause is found.
4. Every wrong answer that reached a shopper is fixed with the shopper
   first, then becomes a new eval case.

## Kill switch

Pulling the switch stops every agent run, and each open ticket goes to
the desk queue with the reason. The code is
[budget_guard.py](../../ch15/budget_guard.py); see a drill with
`python -m ch15.budget_guard kill`. Either the returns desk lead or the
platform on-call may pull it, without asking anyone.
