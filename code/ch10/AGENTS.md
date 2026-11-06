# AGENTS.md: rules for sample_repo (Example Supply Co., invented)

Read this file before the first edit. Keep it under 60 lines.
An AGENTS.md in a subfolder overrides this one for that folder.

## Requirements
- Refunds: an unopened item gets a full refund. A damaged item gets
  a full refund even when opened. An opened, undamaged item pays the
  RESTOCK_PERCENT fee.
- Shipping: an order of FREE_FROM cents or more ships free. A
  smaller order pays FLAT_FEE.
- Money is whole cents in an int. Never use float for money.
- The person who buys is the "shopper" in names and messages.

## Technical decisions
- Python 3.12, standard library only.
- Tests use unittest: python -m unittest test_refunds test_shipping
- A one-line bug gets a one-line fix: no new modules, classes, or
  settings.

## Standards
- Run the team's linter and type checker before each commit. In this
  sample, python -m py_compile on each changed file is the floor.
- The same checks run as a pre-commit hook, so a commit that fails
  them never reaches review.
- Size limits: one fix per diff, at most 20 changed lines, and no
  function over 40 lines.
- Prove the root cause before the edit, and fix that cause.
- Build only what the ticket asks. Never push; a person merges.

## Test strategy
- Start from a failing test that shows the bug.
- Test behavior: what a shopper pays or gets back, in cents.
- No coverage targets. Never mock the function under test.
- Run the listed tests after every edit and the full suite on the
  final diff.
- Never weaken, skip, or delete a test to make it pass.

## Lessons
- Refund run: setting RESTOCK_PERCENT to 0 made the damaged test
  pass and broke the fee rule. Change the condition, never the fee.
- A hook refusal still costs a try. Read the skill's file list first.
