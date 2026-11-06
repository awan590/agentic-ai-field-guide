"""Solution: close the two link holes without losing normal tasks.

    python -m ch13.solution_links

With every defense on, two attacks still carry data out in an
image: a reference-style image (P4) and an allowed image proxy that
fetches another host (P5). strict_links checks every URL wherever it
sits, and drops an allowed URL that carries a second URL inside it.
lockdown drops every URL, which also stops both attacks but breaks
normal tasks that need the store's own links. Data is synthetic.
"""
import sys
from urllib.parse import unquote

from ch13 import cases
from ch13.injection_suite import suite
from ch13.pii_filter import ALLOWED_HOSTS, URL, host, safe_markdown


def strict_links(text):
    """Keep a URL only if its host is allowed and it holds no URL."""
    def fix(m):
        url = m.group()
        rest = unquote(url.split("://", 1)[1])
        if host(url) in ALLOWED_HOSTS and "://" not in rest:
            return url
        return "[link removed]"
    return URL.sub(fix, safe_markdown(text))


def lockdown(text):
    """The blunt fix: no URLs at all."""
    return URL.sub("[link removed]", text)


def main():
    n, t = len(cases.ATTACKS), len(cases.TASKS)
    print(f"All defenses on; {n} attacks, {t} normal tasks "
          "(synthetic).")
    print(f"{'link filter':15}{'attacks that worked':22}normal right")
    rows = [("inline only", safe_markdown), ("lockdown", lockdown),
            ("strict", strict_links)]
    for name, links in rows:
        worked, right = suite("all", links)
        names = " (" + " ".join(worked) + ")" if worked else ""
        print(f"{name:15}{len(worked):>2} of {n}{names:<14}"
              f"{right:>2} of {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
