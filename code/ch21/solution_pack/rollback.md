# Rollback

A version is one bundle: prompt, model name, tools, and policy. A
rollback moves the live pointer back to the last good bundle. It
copies no files and rebuilds nothing. The code is
[release.py](../../ch16/release.py).

## Steps

1. Check the alert or the report that points to the new version.
2. Roll the pointer back to the last good version. To see a bad
   version go to 5% of traffic and come back, run
   `python -m ch16.release canary`.
3. Run the smoke test: `python -m ch16.smoke_test` must pass.
4. Tell the returns desk lead, and write what happened in the log.

## Last rehearsal

Week 0 of go-live (synthetic): the platform on-call lead ran the
canary, the rollback, and the smoke test on staging, with the FDE
watching and saying nothing. Each step was timed and written down.
