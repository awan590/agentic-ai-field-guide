"""Chapter 10 task: one skill for a repeated fix, with its check.

    python -m ch10.solution_skill

The repeated task: a shipping rule fails its test at the exact
threshold. The skill lives in skills/shipping_fix/SKILL.md. It lists
one file the agent may edit, the tests to run, and a cap of two
tries. The stand-in model first reaches for the refund file, which
the hook blocks, then makes the real fix. The task is done when the
tests pass in the sandbox and every step of the skill checks PASS.
"""
import sys

from ch10.skill_check import report

SCRIPT = [
    {"plan": "change the refund rule too", "file": "refunds.py",
     "old": "    if opened:", "new": "    if opened and not damaged:"},
    {"plan": "count exactly $50.00 as free", "file": "shipping.py",
     "old": "subtotal > FREE_FROM", "new": "subtotal >= FREE_FROM"},
]

if __name__ == "__main__":
    sys.exit(0 if report("shipping_fix", SCRIPT) else 1)
