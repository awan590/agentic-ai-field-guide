"""A guard between a computer-use agent and the screen.

    python -m ch11.click_guard

The model looks at a screenshot and proposes one action at a time:
open a page, click a button, type text. Before any action runs, the
guard checks it in code. The action must be on the action allowlist,
the page must be https on an allowed host, and a click on a button
with real-world consequences, or typed text that presses Enter, waits
for a person. A screenshot or a scroll with no page changes nothing,
so it needs no host. Each action gets ALLOW, BLOCK, or ASK. The
portal, its pages, and the trace are synthetic.
"""
import re
import sys
from urllib.parse import urlsplit

ACTIONS = {"screenshot", "open", "click", "type", "scroll"}
HOSTS = {"portal.example-supply.test"}
RISKY = re.compile(r"\b(place order|order now|complete order|pay|"
                   r"payment|submit|delete|send|accept|buy|check ?out|"
                   r"purchase|confirm)\b", re.IGNORECASE)


def check(action):
    """Return ("ALLOW" or "BLOCK" or "ASK", why) for one action."""
    kind = action.get("action")
    if kind not in ACTIONS:
        return "BLOCK", f"action {kind!r} is not on the allowlist"
    if kind in ("screenshot", "scroll") and "url" not in action:
        return "ALLOW", ""
    url = urlsplit(action.get("url", ""))
    if url.scheme != "https":
        return "BLOCK", "only https pages are allowed"
    if url.hostname not in HOSTS:
        return "BLOCK", "this host is not on the allowlist"
    if kind == "click" and RISKY.search(action.get("target", "")):
        return "ASK", "this click has real-world consequences"
    if kind == "type" and "\n" in action.get("text", ""):
        return "ASK", "pressing Enter can submit a form"
    return "ALLOW", ""


def run(actions, approve):
    """Check each action just before it would run, one at a time.

    Return (verdict, ran, action, why) for every action.
    """
    log = []
    for action in actions:
        verdict, why = check(action)
        ran = verdict == "ALLOW"
        if verdict == "ASK":
            ran = bool(approve(action))
            why = "person said " + ("yes; it ran" if ran else
                                    "no; it did not run")
        log.append((verdict, ran, action, why))
    return log


SITE = "https://portal.example-supply.test"
TRACE = [
    {"action": "open", "url": SITE + "/reorder"},
    {"action": "click", "url": SITE + "/reorder",
     "target": "Cable ties, pack of 100"},
    {"action": "type", "url": SITE + "/reorder", "target": "Quantity",
     "text": "10"},
    {"action": "open", "why": "the page says to verify the account",
     "url": "https://portal.example-supply.test.login-check.test/"},
    {"action": "open", "url": "http://portal.example-supply.test/"},
    {"action": "click", "url": SITE + "/cart", "target": "Place order"},
    {"action": "download", "url": SITE + "/orders",
     "target": "Invoice PDF"},
]


def main():
    print("Synthetic portal and trace; each action checked before it "
          "runs.")
    log = run(TRACE, approve=lambda action: True)
    for verdict, _, action, why in log:
        url = urlsplit(action["url"])
        shown = action.get("target") or \
            f"{url.netloc}{url.path} ({url.scheme})"
        if "text" in action:
            shown = f'"{action["text"]}" into {shown}'
        print(f"{verdict:6} {action['action']:9}{shown}")
        if "why" in action:
            print(f"{'':16}model: {action['why']}")
        if why:
            print(f"{'':16}{why}")
    verdicts = [verdict for verdict, _, _, _ in log]
    print(f"ran {sum(ran for _, ran, _, _ in log)} of {len(log)}; "
          f"blocked {verdicts.count('BLOCK')}; "
          f"asked a person {verdicts.count('ASK')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
