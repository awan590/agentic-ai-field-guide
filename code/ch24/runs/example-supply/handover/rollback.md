# Rollback

A version is one bundle: prompt, model name, tools, and policy. The
live bundle is [4618f1530831](../bundle.json).

## Steps

1. Move the live pointer back to the last good bundle.
2. Run `python -m ch16.smoke_test`; it must pass.
3. Tell the returns desk lead, and write what happened in the log.

## Last rehearsal

Week 0 of go-live (synthetic): the platform on-call lead rolled back to the last good bundle on staging and ran the smoke test, with the FDE watching.
