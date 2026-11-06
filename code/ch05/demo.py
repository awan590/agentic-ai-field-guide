"""Talk to the orders server the way a host does: over stdio.

Each session starts the server as a subprocess with one synthetic
token in its environment, writes one JSON request per line, closes
stdin, and pairs the replies with the requests by id.

    python -m ch05.demo          # one line per reply
    python -m ch05.demo wire     # one request and reply in full
"""
import json
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {}}
GRANTS = {"tok-support": ["orders:read", "policy:read"],
          "tok-refunds": ["refunds:write"]}
POLICY = "supply://policy/refunds"
REFUND = {"order_id": "A-1001", "amount": 15.9,
          "reason": "arrived damaged"}


def req(rid, method, meta=True, **params):
    """Build one request; every request carries its own _meta."""
    if meta:
        params["_meta"] = META
    return {"jsonrpc": "2.0", "id": rid, "method": method,
            "params": params}


def call(rid, name, **args):
    return req(rid, "tools/call", name=name, arguments=args)


def session(token, requests):
    """Start the server, send every request, return replies by id."""
    env = {"ES_TOKEN": token, "ES_GRANTS": json.dumps(GRANTS)}
    lines = "".join(json.dumps(r) + "\n" for r in requests)
    proc = subprocess.run(
        [sys.executable, "-E", "-s", "-m", "ch05.orders_server"],
        input=lines, capture_output=True, text=True, cwd=CODE,
        env=env, timeout=30, check=True)
    replies = [json.loads(x) for x in proc.stdout.splitlines()]
    return {r["id"]: r for r in replies}


def brief(reply):
    """One short line for a reply."""
    if "error" in reply:
        e = reply["error"]
        return f"error {e['code']}: {e['message']}"
    r = reply["result"]
    if "supportedVersions" in r:
        info = r["_meta"]["io.modelcontextprotocol/serverInfo"]
        return f"{info['name']} {info['version']} speaks " + \
            ", ".join(r["supportedVersions"])
    if "tools" in r:
        return "tools: " + ", ".join(t["name"] for t in r["tools"])
    if "resources" in r:
        uris = (x["uri"] for x in r["resources"])
        return "resources: " + ", ".join(uris)
    if "contents" in r:
        return r["contents"][0]["text"].splitlines()[0]
    data = r["structuredContent"]
    if r["isError"]:
        return "isError: " + data["error"]
    if "request_id" in data:
        return f"{data['request_id']} {data['status']}"
    return f"{data['id']} {data['status']}, total {data['total']}"


def run(token, steps):
    print(f"{token} ({', '.join(GRANTS.get(token, ['no grant']))})")
    replies = session(token, [r for _, r in steps])
    for label, r in steps:
        print(f"  {label}")
        print(f"    {brief(replies[r['id']])}")


def main():
    if sys.argv[1:] == ["wire"]:
        ask = call(5, "request_refund", **REFUND)
        reply = session("tok-support", [ask])[5]
        print(json.dumps(ask, indent=2, sort_keys=True))
        print(json.dumps(reply, indent=2, sort_keys=True))
        return
    run("tok-support", [
        ("server/discover", req(1, "server/discover")),
        ("tools/list", req(2, "tools/list")),
        ("resources/list", req(3, "resources/list")),
        ("get_order A-1001", call(4, "get_order", order_id="A-1001")),
        ("request_refund A-1001", call(5, "request_refund", **REFUND)),
        ("tools/list without _meta", req(6, "tools/list", meta=False)),
    ])
    run("tok-refunds", [
        ("tools/list", req(1, "tools/list")),
        ("request_refund A-1004", call(
            2, "request_refund", order_id="A-1004", amount=38.75,
            reason="never arrived")),
        ("request_refund A-1001", call(3, "request_refund", **REFUND)),
        ("get_order A-1001", call(4, "get_order", order_id="A-1001")),
        ("read " + POLICY, req(5, "resources/read", uri=POLICY)),
    ])
    run("tok-revoked", [("tools/list", req(1, "tools/list"))])


if __name__ == "__main__":
    main()
