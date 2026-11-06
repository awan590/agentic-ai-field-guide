# Eval gate

Any change to the prompt, the model name, the tools, or the policy
makes a new version, and every new version passes the gate before it
takes traffic.

## Gate command

`python -m ch12.gate FILE` runs the candidate prompt and the released
prompt on the same cases. It prints GATE PASS or GATE FAIL and exits 1
on FAIL. The code is [gate.py](../../ch12/gate.py). When the desk
reports a new kind of wrong answer, add it as a case first.
