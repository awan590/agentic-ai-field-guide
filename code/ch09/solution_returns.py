"""Chapter 9 task: a returns worker, and no task handled twice.

    python -m ch09.solution_returns

The returns worker owns damaged items and their refunds, so the
supervisor sends T-3 to one owner and the ping-pong never starts.
The run then sends every task again, as a shopper's retry would,
and the board turns each one away before any model call.
"""
from collections import Counter

from ch09.supervisor import TASKS, Agent, desk, run_desk, summary

RETURNS = Agent(
    "returns", "You settle damaged items: claim, label, refund.",
    ["get_order(order_id): status and items",
     "file_claim(order_id, note): damage claim with the carrier",
     "issue_refund(order_id, amount, reason): needs approval"],
    owns={"damage", "money"})


def desk_with_returns():
    """Billing and shipping as before, with returns added last."""
    return dict(desk(), returns=RETURNS)


def twice(board):
    """Tasks the board finished more than once: should be none."""
    counts = Counter(task for task, _ in board.log)
    return sorted(task for task, n in counts.items() if n > 1)


def main():
    r = run_desk(desk_with_returns(), TASKS + TASKS)
    print("\n".join(r["lines"]))
    print(summary(r))
    print(f"finished: {len(r['board'].log)} tasks, "
          f"retries turned away: {r['duplicate']}, "
          f"twice: {', '.join(twice(r['board'])) or 'none'}")


if __name__ == "__main__":
    main()
