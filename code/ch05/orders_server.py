"""The Example Supply orders server, written at the protocol level.

MCP revision 2026-07-28 over stdio: one JSON-RPC 2.0 message per
line, no handshake, and every request carries its own _meta. handle()
answers one request and keeps no state between calls, so tests call
it in process; main() is the stdio loop a host starts as a subprocess.

Credentials come from the environment, as the spec asks of stdio
servers. ES_TOKEN is the caller's token; ES_GRANTS maps tokens to
scopes and stands in for the service that issues tokens.

    python -m ch05.orders_server
"""
import json
import os
import sys

from ch05 import data

VERSION = "2026-07-28"
SERVER = {"name": "example-supply-orders", "version": "0.5.0"}
M = "io.modelcontextprotocol/"
NO_TOKEN, NO_SCOPE = -31401, -31403   # outside the reserved range


class RpcError(Exception):
    """A refusal that becomes a JSON-RPC error object."""

    def __init__(self, code, message, detail=None):
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail


def tool(fn, scope, description, **props):
    """One tool: its function, the scope it needs, its input schema."""
    return {"fn": fn, "scope": scope, "description": description,
            "inputSchema": {"type": "object", "properties": props,
                            "required": list(props),
                            "additionalProperties": False}}


def get_order(args):
    order = data.get_order(args["order_id"])
    return order, "error" in order


def request_refund(args):
    """Check the order, then record a request. Nothing is paid."""
    order = data.get_order(args["order_id"])
    if "error" in order:
        return order, True
    if order["status"] not in ("shipped", "delivered"):
        return {"error": f"order is {order['status']}"}, True
    if not 0 < args["amount"] <= order["total"]:
        return {"error": f"amount must be over 0 and at most "
                         f"{order['total']}"}, True
    saved = data.record_refund(order["id"], args["amount"],
                               args["reason"])
    return saved, False


TOOLS = {
    "get_order": tool(
        get_order, "orders:read",
        "Look up one order by its id, such as A-1001.",
        order_id={"type": "string"}),
    "request_refund": tool(
        request_refund, "refunds:write",
        "Ask for a refund on a shipped or delivered order. Records "
        "a request for a person to approve; it does not pay.",
        order_id={"type": "string"}, amount={"type": "number"},
        reason={"type": "string"}),
}

RESOURCES = {
    "supply://policy/refunds": {
        "scope": "policy:read", "name": "refund-policy",
        "description": "The rules every refund request must meet.",
        "mimeType": "text/plain", "read": lambda: data.REFUND_POLICY},
}


def check_meta(params):
    """Every request names its protocol version and capabilities."""
    meta = params.get("_meta") if isinstance(params, dict) else None
    if not isinstance(meta, dict) or M + "protocolVersion" not in meta \
            or not isinstance(meta.get(M + "clientCapabilities"), dict):
        raise RpcError(-32602, "Missing required _meta fields")
    asked = meta[M + "protocolVersion"]
    if asked != VERSION:
        raise RpcError(-32022, "Unsupported protocol version",
                       {"supported": [VERSION], "requested": asked})


def scopes_for(env):
    """The scopes granted to the caller's token, or a refusal."""
    try:
        grants = json.loads(env.get("ES_GRANTS", "{}"))
    except ValueError:
        grants = {}
    token = env.get("ES_TOKEN", "")
    if not token or not isinstance(grants, dict) or token not in grants:
        raise RpcError(NO_TOKEN, "No valid credential in ES_TOKEN")
    return set(grants[token])


def require(scopes, scope, what):
    if scope not in scopes:
        raise RpcError(NO_SCOPE, f"{what} needs scope {scope}",
                       {"requiredScope": scope})


TYPES = {"string": str, "number": (int, float)}


def check_args(schema, args):
    """Name the first problem with the arguments, or return None."""
    props = schema["properties"]
    for name in schema["required"]:
        if name not in args:
            return f"missing argument: {name}"
    for name, value in sorted(args.items()):
        if name not in props:
            return f"unknown argument: {name}"
        kind = props[name]["type"]
        if isinstance(value, bool) or \
                not isinstance(value, TYPES[kind]):
            return f"{name} must be a {kind}"
    return None


def discover(params, scopes, resources):
    return {"supportedVersions": [VERSION],
            "capabilities": {"tools": {}, "resources": {}},
            "ttlMs": 3600000, "cacheScope": "public"}


def list_tools(params, scopes, resources):
    tools = [{"name": name, "description": t["description"],
              "inputSchema": t["inputSchema"]}
             for name, t in sorted(TOOLS.items())
             if t["scope"] in scopes]
    return {"tools": tools, "ttlMs": 60000, "cacheScope": "private"}


def call_tool(params, scopes, resources):
    name, args = params.get("name"), params.get("arguments", {})
    if name not in TOOLS or not isinstance(args, dict):
        raise RpcError(-32602, f"Unknown tool: {name}")
    require(scopes, TOOLS[name]["scope"], name)
    problem = check_args(TOOLS[name]["inputSchema"], args)
    if problem:
        payload, failed = {"error": problem}, True
    else:
        payload, failed = TOOLS[name]["fn"](args)
    text = json.dumps(payload, sort_keys=True)
    return {"content": [{"type": "text", "text": text}],
            "structuredContent": payload, "isError": failed}


def list_resources(params, scopes, resources):
    items = [{"uri": uri, "name": r["name"],
              "description": r["description"],
              "mimeType": r["mimeType"]}
             for uri, r in sorted(resources.items())
             if r["scope"] in scopes]
    return {"resources": items, "ttlMs": 60000, "cacheScope": "private"}


def read_resource(params, scopes, resources):
    uri = params.get("uri")
    if not isinstance(uri, str) or uri not in resources:
        raise RpcError(-32602, "Resource not found", {"uri": uri})
    res = resources[uri]
    require(scopes, res["scope"], uri)
    return {"contents": [{"uri": uri, "mimeType": res["mimeType"],
                          "text": res["read"]()}],
            "ttlMs": 0, "cacheScope": "private"}


METHODS = {"server/discover": discover, "tools/list": list_tools,
           "tools/call": call_tool, "resources/list": list_resources,
           "resources/read": read_resource}


def handle(request, env, resources=RESOURCES):
    """Answer one JSON-RPC request from the request and env alone."""
    rid = request.get("id")
    try:
        method = request.get("method")
        if request.get("jsonrpc") != "2.0":
            raise RpcError(-32600, "Invalid Request")
        if method not in METHODS:
            raise RpcError(-32601, f"Method not found: {method}")
        params = request.get("params", {})
        check_meta(params)
        scopes = set()
        if method != "server/discover":
            scopes = scopes_for(env)
        result = METHODS[method](params, scopes, resources)
    except RpcError as e:
        error = {"code": e.code, "message": e.message}
        if e.detail is not None:
            error["data"] = e.detail
        return {"jsonrpc": "2.0", "id": rid, "error": error}
    result["resultType"] = "complete"
    result["_meta"] = {M + "serverInfo": SERVER}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def serve(lines, env, write, resources=RESOURCES):
    """Read one message per line; write one reply per request."""
    for line in lines:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            msg = None
        if not isinstance(msg, dict):
            write({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": "Parse error"}})
        elif "id" in msg:            # no id: a notification, no reply
            write(handle(msg, env, resources))


def main(resources=RESOURCES):
    def write(reply):
        sys.stdout.write(json.dumps(reply, sort_keys=True) + "\n")
        sys.stdout.flush()
    serve(sys.stdin, dict(os.environ), write, resources)


if __name__ == "__main__":
    main()
