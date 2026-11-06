# Returns agent handover pack: Example Supply

Example Supply Co. is the book's invented parts store, and every name
and number in this pack is synthetic. The pack is what the returns
desk and the platform team run the returns agent from after the
forward deployed engineer (FDE) leaves. Each part points to the code
that does the work; nothing here copies that code.

## Contents

- [Runbook](runbook.md): daily checks, when something breaks, kill switch
- [Owners](owners.md): one owner and one backup at Example Supply per area
- [Rollback](rollback.md): back to the last good version in one step
- [Eval gate](evals.md): the gate every change must pass
- [Alerts](alerts.md): what pages whom
- [Data map](data-map.md): what the agent reads and what is kept
- [Contacts](contacts.md): who to call

## Why the agent is live

The pilot gate said SCALE. The readout and its checker are in
[solution_readout.py](../../ch20/solution_readout.py); rerun them with
`python -m ch20.solution_readout`.

## Check this pack

Run `python -m ch21.handover_check FOLDER` from the `code` folder after
every edit, with this pack's folder. It must print HANDOVER OK.
