"""Hands-on solution: a read-only inventory resource.

The server code stays as it is. This module adds one resource with
its own scope, inventory:read, and serves the larger table. No tool
writes stock, so the new data is read-only by construction.

    python -m ch05.solution_inventory
"""
import json

from ch05 import data, orders_server as srv

RESOURCES = dict(srv.RESOURCES)
RESOURCES["supply://inventory/stock"] = {
    "scope": "inventory:read", "name": "stock-levels",
    "description": "Units on hand for each SKU. Read-only.",
    "mimeType": "application/json",
    "read": lambda: json.dumps(data.stock_levels(), sort_keys=True)}


def handle(request, env):
    return srv.handle(request, env, RESOURCES)


if __name__ == "__main__":
    srv.main(RESOURCES)
