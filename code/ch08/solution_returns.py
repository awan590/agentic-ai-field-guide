"""Chapter 8 task: the returns flow as a router plus one agent step.

    python -m ch08.solution_returns          # a small model routes
    python -m ch08.solution_returns rule     # a keyword rule routes

Routine messages take the fixed workflow. What the router labels
"other" goes to one agent step with a tight step cap, and a run
the cap stops goes to a person. The task is done when the hybrid
gets at least as many right as the free agent at no more than
half of its cost per task.
"""
import sys

from ch08.compare import (agent, labeled_cases, load_prices,
                          model_router, report, rule_router,
                          workflow)

AGENT_STEPS = 4          # the agent step may make 4 model calls
MAX_SHARE = 0.50         # target: half the agent's cost or less


def agent_step(case, run):
    """The one agent step, on a shorter leash than the free agent."""
    return agent(case, run, max_steps=AGENT_STEPS)


def hybrid(router):
    """The workflow, with the agent step in place of the hatch."""
    return lambda case, run: workflow(case, router, run,
                                      fallback=agent_step)


def check(free, mixed):
    """Compare the hybrid with the free agent against the targets."""
    share = mixed["cost"] / free["cost"]
    ok = mixed["right"] >= free["right"] and share <= MAX_SHARE
    return share, ok


def main(argv):
    router = rule_router if argv[:1] == ["rule"] else model_router
    print(f"router: {router.__name__}")
    designs = {"workflow": lambda c, r: workflow(c, router, r),
               "free agent": agent, "hybrid": hybrid(router)}
    results = report(designs, labeled_cases(), load_prices())
    mixed = results["hybrid"]
    share, ok = check(results["free agent"], mixed)
    print(f"hybrid: ${mixed['cost'] / 1000:.6f} per task, "
          f"{100 * share:.1f}% of the agent's cost  "
          f"{'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main(sys.argv[1:])
