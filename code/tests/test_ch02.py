import io
import json
import os
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from ch02 import mini_agent as ma
from ch02 import order_status as os_task
from ch02 import real_model as rm
from ch02.store import ORDERS, get_order
from ch02.stub_model import StandInModel

LOOKUP = {"tool_calls": [{"name": "get_order",
                          "args": {"order_id": "A-1001"}}]}
ANSWER = {"content": "A-1001 shipped."}


def events(result, kind):
    return [e for e in result["trace"] if e["event"] == kind]


class StoreTest(unittest.TestCase):
    def test_six_to_ten_orders_with_matching_totals(self):
        self.assertTrue(6 <= len(ORDERS) <= 10)
        for order in ORDERS.values():
            total = sum(i["qty"] * i["price"] for i in order["items"])
            self.assertAlmostEqual(order["total"], total, places=2)

    def test_get_order_returns_a_copy(self):
        order = get_order("a-1001 ")
        order["status"] = "lost"
        self.assertEqual(get_order("A-1001")["status"], "shipped")

    def test_missing_order_is_data(self):
        self.assertIn("error", get_order("A-9999"))


class LoopTest(unittest.TestCase):
    def test_done_after_lookup(self):
        result = ma.run_agent(StandInModel([LOOKUP, ANSWER]),
                              ma.TOOLS, "Has A-1001 shipped?")
        self.assertEqual(result["stop"], "done")
        self.assertEqual(result["steps"], 2)
        self.assertEqual(result["answer"], "A-1001 shipped.")
        got = events(result, "tool_result")[0]["result"]
        self.assertEqual(got["status"], "shipped")

    def test_step_cap(self):
        model = StandInModel([LOOKUP] * 20)
        result = ma.run_agent(model, ma.TOOLS, "Loop", max_steps=3)
        self.assertEqual((result["stop"], result["steps"]),
                         ("step cap", 3))
        self.assertIsNone(result["answer"])
        self.assertEqual(model.calls, 3)

    def test_time_cap(self):
        def slow(order_id):
            time.sleep(0.05)
            return get_order(order_id)
        tools = {"get_order": dict(ma.TOOLS["get_order"], fn=slow)}
        result = ma.run_agent(StandInModel([LOOKUP] * 20), tools,
                              "Slow", max_seconds=0.02)
        self.assertEqual((result["stop"], result["steps"]),
                         ("time cap", 1))

    def test_token_cap(self):
        result = ma.run_agent(StandInModel([LOOKUP] * 20), ma.TOOLS,
                              "Tokens", max_tokens=150)
        self.assertEqual(result["stop"], "token cap")
        self.assertGreaterEqual(result["tokens"], 150)
        self.assertLess(result["steps"], 8)

    def test_unknown_tool_is_never_called(self):
        ran = []
        tools = {"get_order": ma.tool(lambda order_id: ran.append(1),
                                      "Look up", order_id={})}
        script = [{"tool_calls": [{"name": "delete_order",
                                   "args": {"order_id": "A-1001"}}]},
                  ANSWER]
        result = ma.run_agent(StandInModel(script), tools, "Delete")
        self.assertEqual(ran, [])
        self.assertEqual(events(result, "tool_result")[0]["result"],
                         {"error": "unknown tool: delete_order"})
        self.assertEqual(result["stop"], "done")

    def test_tool_errors_come_back_as_data(self):
        out = ma.call_tool(ma.TOOLS, "get_order", {"id": "A-1001"})
        self.assertTrue(out["error"].startswith("TypeError"))

    def test_tool_call_is_traced_before_its_result(self):
        result = ma.run_agent(StandInModel([LOOKUP, ANSWER]),
                              ma.TOOLS, "Order")
        kinds = [e["event"] for e in result["trace"]]
        self.assertEqual(kinds, ["task", "model", "tool_call",
                                 "tool_result", "model", "stop"])

    def test_tool_message_answers_its_call(self):
        model = StandInModel([LOOKUP, ANSWER])
        seen = []
        complete = model.complete
        model.complete = lambda m, t: seen.append(list(m)) or complete(
            m, t)
        ma.run_agent(model, ma.TOOLS, "Order")
        call, result = seen[1][1], seen[1][2]
        self.assertEqual(result["role"], "tool")
        self.assertEqual(result["tool_call_id"],
                         call["tool_calls"][0]["id"])
        self.assertEqual(json.loads(result["content"])["id"], "A-1001")

    def test_demo_trace_lines_fit_the_page(self):
        for name in ma.DEMOS:
            buf = io.StringIO()
            with redirect_stdout(buf):
                ma.main([name])
            lines = buf.getvalue().splitlines()
            self.assertTrue(all(len(ln) <= 72 for ln in lines))
            self.assertIn("stop", lines[-1])


CANNED = {
    "id": "msg_test", "type": "message", "role": "assistant",
    "content": [
        {"type": "text", "text": "Checking the order."},
        {"type": "tool_use", "id": "toolu_1", "name": "get_order",
         "input": {"order_id": "A-1001"}}],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 412, "output_tokens": 58},
}


class RealModelTest(unittest.TestCase):
    def test_from_api(self):
        msg = rm.from_api(CANNED)
        self.assertEqual(msg["content"], "Checking the order.")
        self.assertEqual(msg["tool_calls"], [
            {"id": "toolu_1", "name": "get_order",
             "args": {"order_id": "A-1001"}}])
        self.assertEqual(msg["usage"], {"input_tokens": 412,
                                        "output_tokens": 58})

    def test_to_api_groups_tool_results(self):
        call = {"name": "get_order", "args": {"order_id": "A-1001"}}
        messages = [
            {"role": "user", "content": "Two orders?"},
            {"role": "assistant", "content": "",
             "tool_calls": [dict(call, id="t1"), dict(call, id="t2")]},
            {"role": "tool", "tool_call_id": "t1", "content": "{}"},
            {"role": "tool", "tool_call_id": "t2", "content": "{}"}]
        body = rm.to_api(messages, ma.tool_specs(ma.TOOLS))
        roles = [m["role"] for m in body["messages"]]
        self.assertEqual(roles, ["user", "assistant", "user"])
        self.assertEqual(body["messages"][1]["content"][0]["type"],
                         "tool_use")
        ids = [b["tool_use_id"] for b in body["messages"][2]["content"]]
        self.assertEqual(ids, ["t1", "t2"])
        self.assertIn("input_schema", body["tools"][0])

    def test_round_trip(self):
        msg = rm.from_api(CANNED)
        body = rm.to_api([{"role": "user", "content": "Hi"}, msg], [])
        self.assertEqual(body["messages"][1]["content"],
                         CANNED["content"])
        self.assertNotIn("tools", body)

    def test_complete_sends_one_request(self):
        sent = []

        def fake_urlopen(request, timeout):
            sent.append(request)
            return io.BytesIO(json.dumps(CANNED).encode())
        env = {"ANTHROPIC_API_KEY": "test-value"}
        with mock.patch.dict(os.environ, env), mock.patch.object(
                rm.urllib.request, "urlopen", fake_urlopen):
            msg = rm.AnthropicModel().complete(
                [{"role": "user", "content": "Hi"}], [])
        self.assertEqual(msg["tool_calls"][0]["name"], "get_order")
        self.assertEqual(sent[0].full_url, rm.API_URL)
        self.assertEqual(sent[0].get_header("Anthropic-version"),
                         rm.API_VERSION)
        body = json.loads(sent[0].data)
        self.assertEqual(body["model"], "claude-haiku-5-5")

    def test_main_without_key_exits_clearly(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as stop:
                rm.main([])
        self.assertIn("ANTHROPIC_API_KEY", str(stop.exception))


class OrderStatusTaskTest(unittest.TestCase):
    def test_returns_least_data(self):
        self.assertEqual(os_task.order_status("A-1005"), {
            "id": "A-1005", "status": "shipped",
            "placed": "2026-10-29"})

    def test_missing_order_is_data(self):
        self.assertIn("error", os_task.order_status("A-0000"))

    def test_registered_next_to_get_order(self):
        self.assertEqual(sorted(os_task.TOOLS),
                         ["get_order", "order_status"])
        specs = ma.tool_specs(os_task.TOOLS)
        self.assertTrue(all(s["description"] for s in specs))

    def test_agent_uses_it(self):
        result = ma.run_agent(StandInModel(os_task.SCRIPT),
                              os_task.TOOLS, "Where is A-1005?")
        self.assertEqual(result["stop"], "done")
        got = events(result, "tool_result")[0]["result"]
        self.assertNotIn("customer", got)
        self.assertEqual(got["status"], "shipped")


if __name__ == "__main__":
    unittest.main()
