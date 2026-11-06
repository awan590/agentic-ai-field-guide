---
name: shipping-fix
description: Fix a failing shipping test. Use when test_shipping fails.
files: shipping.py
tests: test_shipping
cap: 2
---
# Fix a failing shipping test

1. [sandbox] Work in a throwaway copy, never the original.
2. [test-first] Run the listed tests and read the failure first.
3. [one-edit] Make one exact text replacement per try.
4. [test-after] Run the listed tests again after every edit.
5. [cap] Stop at the try cap and hand the notes to a person.
6. [approval] End with a diff for human approval. Never push.
