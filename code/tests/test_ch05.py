import json
import subprocess
import sys
import unittest
from pathlib import Path

from ch05 import data, demo
from ch05 import orders_server as srv
from ch05 import solution_inventory as inv

CODE = Path(__file__).resolve().parent.parent
M = "io.modelcontextprotocol/"
META = {M + "protocolVersion": "2026-07-28",
        M + "clientCapabilities": {}}
GRANTS = json.dumps({"tok-support": ["orders:read", "policy:read"],
                     "tok-refunds": ["refunds:write"],
                     "tok-stock": ["inventory:read"]})
POLICY = "supply://policy/refunds"
STOCK = "supply://inventory/stock"


def ask(method, token="tok-support", handler=srv.handle, meta=META,
        **params):
    if meta is not None:
        params["_meta"] = meta
    request = {"jsonrpc": "2.0", "id": 7, "method": method,
               "params": params}
    return handler(request, {"ES_TOKEN": token, "ES_GRANTS": GRANTS})


def call(name, token="tok-refunds", **args):
    return ask("tools/call", token, name=name, arguments=args)


def code(reply):
    return reply["error"]["code"]


class ProtocolTest(unittest.TestCase):
    def test_discover_works_without_a_token(self):
        result = ask("server/discover", token="")["result"]
        self.assertEqual(result["supportedVersions"], ["2026-07-28"])
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["cacheScope"], "public")
        self.assertGreaterEqual(result["ttlMs"], 0)

    def test_every_result_names_the_server(self):
        reply = ask("tools/list")
        self.assertEqual(reply["id"], 7)
        self.assertEqual(reply["result"]["_meta"][M + "serverInfo"],
                         srv.SERVER)

    def test_missing_meta_is_invalid_params(self):
        self.assertEqual(code(ask("tools/list", meta=None)), -32602)
        half = {M + "protocolVersion": "2026-07-28"}
        self.assertEqual(code(ask("tools/list", meta=half)), -32602)

    def test_old_version_is_refused_with_the_supported_list(self):
        old = dict(META, **{M + "protocolVersion": "2025-11-25"})
        error = ask("tools/list", meta=old)["error"]
        self.assertEqual(error["code"], -32022)
        self.assertEqual(error["data"], {"supported": ["2026-07-28"],
                                         "requested": "2025-11-25"})

    def test_no_handshake_method(self):
        self.assertEqual(code(ask("initialize")), -32601)

    def test_wrong_jsonrpc_version_is_invalid_request(self):
        reply = srv.handle({"jsonrpc": "1.0", "id": 1,
                            "method": "tools/list"}, {})
        self.assertEqual(code(reply), -32600)


class AuthTest(unittest.TestCase):
    def setUp(self):
        data.REFUNDS.clear()

    def test_missing_or_unknown_token_is_unauthenticated(self):
        self.assertEqual(code(ask("tools/list", token="")), -31401)
        self.assertEqual(code(ask("tools/list", token="tok-x")), -31401)
        reply = srv.handle({"jsonrpc": "2.0", "id": 1,
                            "method": "tools/list",
                            "params": {"_meta": META}},
                           {"ES_TOKEN": "tok-support",
                            "ES_GRANTS": "not json"})
        self.assertEqual(code(reply), -31401)

    def test_tools_list_shows_only_granted_tools(self):
        for token, names in [("tok-support", ["get_order"]),
                             ("tok-refunds", ["request_refund"]),
                             ("tok-stock", [])]:
            result = ask("tools/list", token)["result"]
            got = [t["name"] for t in result["tools"]]
            self.assertEqual(got, names)
            self.assertEqual(result["cacheScope"], "private")

    def test_refund_refused_without_scope_records_nothing(self):
        error = call("request_refund", "tok-support", order_id="A-1001",
                     amount=1.0, reason="test")["error"]
        self.assertEqual(error["code"], -31403)
        self.assertEqual(error["data"],
                         {"requiredScope": "refunds:write"})
        self.assertEqual(data.REFUNDS, {})

    def test_refund_token_cannot_read_orders(self):
        reply = call("get_order", order_id="A-1001")
        self.assertEqual(code(reply), -31403)

    def test_unknown_tool_is_invalid_params(self):
        error = call("pay_out", amount=10)["error"]
        self.assertEqual(error["code"], -32602)
        self.assertEqual(error["message"], "Unknown tool: pay_out")


class ToolTest(unittest.TestCase):
    def setUp(self):
        data.REFUNDS.clear()

    def test_get_order_returns_text_and_structured_content(self):
        result = call("get_order", "tok-support",
                      order_id="a-1001")["result"]
        self.assertFalse(result["isError"])
        order = result["structuredContent"]
        self.assertEqual(order["status"], "shipped")
        self.assertEqual(result["content"][0]["text"],
                         json.dumps(order, sort_keys=True))

    def test_missing_order_is_a_tool_error(self):
        result = call("get_order", "tok-support",
                      order_id="A-9999")["result"]
        self.assertTrue(result["isError"])

    def test_bad_arguments_come_back_as_tool_errors(self):
        cases = [({"order_id": "A-1001", "amount": "lots",
                   "reason": ""},
                  "amount must be a number"),
                 ({"order_id": "A-1001", "amount": True, "reason": ""},
                  "amount must be a number"),
                 ({"order_id": "A-1001", "reason": ""},
                  "missing argument: amount"),
                 ({"order_id": "A-1001", "amount": 1, "reason": "",
                   "approve": True}, "unknown argument: approve")]
        for args, message in cases:
            result = call("request_refund", **args)["result"]
            self.assertTrue(result["isError"])
            self.assertEqual(result["structuredContent"]["error"],
                             message)
        self.assertEqual(data.REFUNDS, {})

    def test_refund_rules_are_checked_by_the_server(self):
        for order_id, amount in [("A-1004", 10), ("A-1002", 10),
                                 ("A-1001", 0), ("A-1001", 15.91),
                                 ("A-9999", 1)]:
            result = call("request_refund", order_id=order_id,
                          amount=amount, reason="test")["result"]
            self.assertTrue(result["isError"], order_id)
        self.assertEqual(data.REFUNDS, {})

    def test_refund_is_a_request_recorded_once(self):
        first = call("request_refund", order_id="A-1001", amount=15.9,
                     reason="damaged")["result"]["structuredContent"]
        again = call("request_refund", order_id="a-1001", amount=5,
                     reason="again")["result"]["structuredContent"]
        self.assertEqual(first, again)
        self.assertEqual(first["status"], "pending review")
        self.assertNotIn("customer", first)
        self.assertEqual(list(data.REFUNDS), ["A-1001"])


class ResourceTest(unittest.TestCase):
    def test_policy_is_listed_and_read(self):
        listed = ask("resources/list")["result"]["resources"]
        self.assertEqual([r["uri"] for r in listed], [POLICY])
        result = ask("resources/read", uri=POLICY)["result"]
        content = result["contents"][0]
        self.assertEqual(content["mimeType"], "text/plain")
        self.assertIn("A person approves every refund", content["text"])
        self.assertEqual(result["cacheScope"], "private")

    def test_unknown_resource_is_not_found(self):
        error = ask("resources/read", uri="supply://secrets")["error"]
        self.assertEqual(error["code"], -32602)
        self.assertEqual(error["data"], {"uri": "supply://secrets"})

    def test_policy_needs_its_scope(self):
        reply = ask("resources/read", "tok-refunds", uri=POLICY)
        self.assertEqual(code(reply), -31403)


class InventoryTest(unittest.TestCase):
    def test_stock_token_reads_inventory(self):
        result = ask("resources/read", "tok-stock", inv.handle,
                     uri=STOCK)["result"]
        stock = json.loads(result["contents"][0]["text"])
        self.assertEqual(stock["BV-012"], 0)
        self.assertEqual(stock, data.stock_levels())

    def test_refund_tool_cannot_read_inventory(self):
        listed = ask("resources/list", "tok-refunds", inv.handle)
        self.assertEqual(listed["result"]["resources"], [])
        error = ask("resources/read", "tok-refunds", inv.handle,
                    uri=STOCK)["error"]
        self.assertEqual(error["code"], -31403)
        self.assertEqual(error["data"],
                         {"requiredScope": "inventory:read"})

    def test_inventory_is_read_only(self):
        self.assertEqual(ask("tools/list", "tok-stock", inv.handle)
                         ["result"]["tools"], [])
        self.assertNotIn(STOCK, srv.RESOURCES)


class StdioTest(unittest.TestCase):
    def test_one_reply_per_request_line(self):
        lines = [json.dumps(demo.req(1, "server/discover")), "",
                 json.dumps({"jsonrpc": "2.0", "method": "note",
                             "params": {}}),
                 "{not json", json.dumps(demo.req(2, "tools/list"))]
        proc = subprocess.run(
            [sys.executable, "-E", "-s", "-m", "ch05.orders_server"],
            input="\n".join(lines) + "\n", capture_output=True,
            text=True, cwd=CODE, timeout=30,
            env={"ES_TOKEN": "tok-support", "ES_GRANTS": GRANTS})
        replies = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([r["id"] for r in replies], [1, None, 2])
        self.assertEqual(replies[1]["error"]["code"], -32700)
        self.assertEqual(proc.returncode, 0)

    def test_demo_session_pairs_replies_by_id(self):
        replies = demo.session("tok-refunds", [
            demo.req(1, "tools/list"), demo.req(2, "resources/list")])
        self.assertEqual(sorted(replies), [1, 2])
        self.assertEqual(replies[2]["result"]["resources"], [])


if __name__ == "__main__":
    unittest.main()
