"""tau2-bench retail domain (Sierra Research, MIT), ported from tau2/domains/retail/tools.py.

Data (db.json, tasks.json, policy.md) is used unmodified from scenarios/sources/tau2-retail. Grading uses tau2's DB
reward (final database equals the gold replay). tau2 also scores retail NL assertions with an LLM judge; that part is
not ported."""

from __future__ import annotations

import copy
import json
import unicodedata
from typing import Any

from ..paths import SCENARIOS
from .jsutil import js_round, js_str
from .tau2 import ToolError, arg, calculate, obj, str_or_empty, string

DIR = SCENARIOS / "sources" / "tau2-retail"

_DB_TEXT: str | None = None


def fresh_retail_db() -> dict:
    global _DB_TEXT
    if _DB_TEXT is None:
        _DB_TEXT = (DIR / "db.json").read_text()
    return json.loads(_DB_TEXT)


RETAIL_TASKS: list[dict] = json.loads((DIR / "tasks.json").read_text())
RETAIL_POLICY = (DIR / "policy.md").read_text()

# tau2 llm_agent.py system prompt with the retail policy
RETAIL_SYSTEM = f"""<instructions>
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy. Always make sure you generate valid JSON only.
</instructions>
<policy>
{RETAIL_POLICY.strip()}
</policy>"""

_order_id = string("The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.")


def _item_ids(d: str) -> dict:
    return {"type": "array", "items": {"type": "string"}, "description": d}


_payment_id = string("The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.")
_address = {
    "address1": string("The first line of the address, such as '123 Main St'."), "address2": string("The second line of the address, such as 'Apt 1' or ''."),
    "city": string("The city, such as 'San Francisco'."), "state": string("The state, such as 'CA'."), "country": string("The country, such as 'USA'."),
    "zip": string("The zip code, such as '12345'."),
}
_addr_keys = ["address1", "address2", "city", "state", "country", "zip"]

RETAIL_TOOLS = [
    {"name": "calculate", "description": "Calculate the result of a mathematical expression, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.",
     "input_schema": obj({"expression": string("The mathematical expression.")}, ["expression"])},
    {"name": "cancel_pending_order", "description": "Cancel a pending order. If the order is already processed or delivered, it cannot be cancelled. The agent needs to explain the cancellation detail and ask for explicit user confirmation (yes/no) to proceed. If the user confirms, the order status will be changed to 'cancelled' and the payment will be refunded. The refund will be added to the user's gift card balance immediately if the payment was made using a gift card, otherwise the refund would take 5-7 business days to process. The function returns the order details after the cancellation.",
     "input_schema": obj({"order_id": _order_id, "reason": string("The reason for cancellation, which should be either 'no longer needed' or 'ordered by mistake'.")}, ["order_id", "reason"])},
    {"name": "exchange_delivered_order_items", "description": "Exchange items in a delivered order to new items of the same product type. For a delivered order, return or exchange can be only done once by the agent. The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.",
     "input_schema": obj({"order_id": _order_id, "item_ids": _item_ids("The item ids to be exchanged, each such as '1008292230'. There could be duplicate items in the list."),
                          "new_item_ids": _item_ids("The item ids to be exchanged for, each such as '1008292230'. There could be duplicate items in the list. Each new item id should match the item id in the same position and be of the same product."),
                          "payment_method_id": _payment_id}, ["order_id", "item_ids", "new_item_ids", "payment_method_id"])},
    {"name": "find_user_id_by_name_zip", "description": "Find user id by first name, last name, and zip code. If the user is not found, the function will return an error message. By default, find user id by email, and only call this function if the user is not found by email or cannot remember email.",
     "input_schema": obj({"first_name": string("The first name of the customer, such as 'John'."), "last_name": string("The last name of the customer, such as 'Doe'."),
                          "zip": string("The zip code of the customer, such as '12345'.")}, ["first_name", "last_name", "zip"])},
    {"name": "find_user_id_by_email", "description": "Find user id by email. If the user is not found, the function will return an error message.",
     "input_schema": obj({"email": string("The email of the user, such as 'something@example.com'.")}, ["email"])},
    {"name": "get_order_details", "description": "Get the status and details of an order.", "input_schema": obj({"order_id": _order_id}, ["order_id"])},
    {"name": "get_product_details", "description": "Get the inventory details of a product.",
     "input_schema": obj({"product_id": string("The product id, such as '6086499569'. Be careful the product id is different from the item id.")}, ["product_id"])},
    {"name": "get_item_details", "description": "Get the inventory details of an item.",
     "input_schema": obj({"item_id": string("The item id, such as '6086499569'. Be careful the item id is different from the product id.")}, ["item_id"])},
    {"name": "get_user_details", "description": "Get the details of a user, including their orders.", "input_schema": obj({"user_id": string("The user id, such as 'sara_doe_496'.")}, ["user_id"])},
    {"name": "list_all_product_types", "description": "List the name and product id of all product types. Each product type has a variety of different items with unique item ids and options. There are only 50 product types in the store.",
     "input_schema": obj({}, [])},
    {"name": "modify_pending_order_address", "description": "Modify the shipping address of a pending order. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.",
     "input_schema": obj({"order_id": _order_id, **_address}, ["order_id", *_addr_keys])},
    {"name": "modify_pending_order_items", "description": "Modify items in a pending order to new items of the same product type. For a pending order, this function can only be called once. The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.",
     "input_schema": obj({"order_id": _order_id, "item_ids": _item_ids("The item ids to be modified, each such as '1008292230'. There could be duplicate items in the list."),
                          "new_item_ids": _item_ids("The item ids to be modified for, each such as '1008292230'. There could be duplicate items in the list. Each new item id should match the item id in the same position and be of the same product."),
                          "payment_method_id": _payment_id}, ["order_id", "item_ids", "new_item_ids", "payment_method_id"])},
    {"name": "modify_pending_order_payment", "description": "Modify the payment method of a pending order. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.",
     "input_schema": obj({"order_id": _order_id, "payment_method_id": _payment_id}, ["order_id", "payment_method_id"])},
    {"name": "modify_user_address", "description": "Modify the default address of a user. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.",
     "input_schema": obj({"user_id": string("The user id, such as 'sara_doe_496'."), **_address}, ["user_id", *_addr_keys])},
    {"name": "return_delivered_order_items", "description": "Return some items of a delivered order. The order status will be changed to 'return requested'. The agent needs to explain the return detail and ask for explicit user confirmation (yes/no) to proceed. The user will receive follow-up email for how and where to return the item.",
     "input_schema": obj({"order_id": _order_id, "item_ids": _item_ids("The item ids to be returned, each such as '1008292230'. There could be duplicate items in the list."),
                          "payment_method_id": string("The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.")},
                         ["order_id", "item_ids", "payment_method_id"])},
    {"name": "transfer_to_human_agents", "description": "Transfer the user to a human agent, with a summary of the user's issue. Only transfer if the user explicitly asks for a human agent, or given the policy and the available tools, you cannot solve the user's issue.",
     "input_schema": obj({"summary": string("A summary of the user's issue.")}, ["summary"])},
]

RETAIL_WRITES = {"cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address", "modify_pending_order_items",
                 "modify_pending_order_payment", "modify_user_address", "return_delivered_order_items"}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.strip()) if not unicodedata.category(c).startswith("M")).lower()


def _round2(x: float) -> float:
    return js_round(x * 100) / 100


def _str_list(v: Any, what: str) -> list[str]:
    if not isinstance(v, list):
        raise ToolError(f"{what} must be a list")
    return [js_str(x) if x is not None else "null" for x in v]


def _get(m: dict, key: Any, err: str) -> dict:
    k = js_str(key) if key is not None else "undefined"
    if k not in m:
        raise ToolError(err)
    return m[k]


def _order(db: dict, a: dict) -> dict:
    return _get(db["orders"], a["order_id"] if "order_id" in a else None, "Order not found")


def _user(db: dict, uid: Any) -> dict:
    return _get(db["users"], uid, "User not found")


def _payment(db: dict, uid: str, pm_id: Any) -> dict:
    return _get(_user(db, uid)["payment_methods"], pm_id, "Payment method not found")


def _variant(db: dict, product_id: str, variant_id: str) -> dict:
    p = _get(db["products"], product_id, "Product not found")
    if variant_id not in p["variants"]:
        raise ToolError("Variant not found")
    return p["variants"][variant_id]


def _address_of(a: dict) -> dict:
    return {k: str_or_empty(a.get(k)) for k in ("address1", "address2", "city", "state", "country", "zip")}


def _swap_diff(db: dict, order: dict, item_ids: list[str], new_ids: list[str], not_found, distinct: bool) -> tuple[float, dict | None]:
    """Price difference of swapping `item_ids` for `new_ids` within `order` (tau2's checks, in tau2's order)."""
    all_ids = [i["item_id"] for i in order["items"]]
    for i in item_ids:
        if item_ids.count(i) > all_ids.count(i):
            raise ToolError(not_found(i))
    if len(item_ids) != len(new_ids):
        raise ToolError("The number of items to be exchanged should match.")
    diff = 0
    last = None
    for k in range(len(item_ids)):
        if distinct and item_ids[k] == new_ids[k]:
            raise ToolError("The new item id should be different from the old item id")
        item = next((i for i in order["items"] if i["item_id"] == item_ids[k]), None)
        if not item:
            raise ToolError(f"Item {item_ids[k]} not found")
        v = _variant(db, item["product_id"], new_ids[k])
        if not v["available"]:
            raise ToolError(f"New item {new_ids[k]} not found or available")
        diff += v["price"] - item["price"]
        last = v
    return diff, last


def run_retail_tool(db: dict, name: str, a: dict) -> Any:
    """Execute one retail tool against `db` (mutating it), returning the tool's result. Raises ToolError on tool errors, as tau2 does."""
    if name == "calculate":
        return calculate(a)
    if name == "cancel_pending_order":
        o = _order(db, a)
        if o["status"] != "pending":
            raise ToolError("Non-pending order cannot be cancelled")
        reason = arg(a, "reason")
        if reason not in ("no longer needed", "ordered by mistake"):
            raise ToolError("Invalid reason")
        refunds = []
        for p in o["payment_history"]:
            refunds.append({"transaction_type": "refund", "amount": p["amount"], "payment_method_id": p["payment_method_id"]})
            _user(db, o["user_id"])
            pm = _payment(db, o["user_id"], p["payment_method_id"])
            if pm["source"] == "gift_card":
                pm["balance"] = _round2((pm.get("balance") or 0) + p["amount"])
        o["status"] = "cancelled"
        o["cancel_reason"] = reason
        o["payment_history"].extend(refunds)
        return o
    if name == "exchange_delivered_order_items":
        o = _order(db, a)
        if o["status"] != "delivered":
            raise ToolError("Non-delivered order cannot be exchanged")
        ids = _str_list(a.get("item_ids"), "item_ids")
        nids = _str_list(a.get("new_item_ids"), "new_item_ids")
        diff = _round2(_swap_diff(db, o, ids, nids, lambda i: f"Number of {i} not found.", False)[0])
        pm = _payment(db, o["user_id"], a.get("payment_method_id") if "payment_method_id" in a else None)
        if pm["source"] == "gift_card" and (pm.get("balance") or 0) < diff:
            raise ToolError("Insufficient gift card balance to pay for the price difference")
        o["status"] = "exchange requested"
        o["exchange_items"] = sorted(ids)
        o["exchange_new_items"] = sorted(nids)
        o["exchange_payment_method_id"] = arg(a, "payment_method_id")
        o["exchange_price_difference"] = diff
        return o
    if name in ("find_user_id_by_name_zip", "find_user_id_by_email"):
        if name == "find_user_id_by_email":
            m = [uid for uid, u in db["users"].items() if _fold(u["email"]) == _fold(str_or_empty(a.get("email")))]
        else:
            m = [uid for uid, u in db["users"].items() if _fold(u["name"]["first_name"]) == _fold(str_or_empty(a.get("first_name")))
                 and _fold(u["name"]["last_name"]) == _fold(str_or_empty(a.get("last_name"))) and u["address"]["zip"] == arg(a, "zip")]
        if len(m) == 1:
            return m[0]
        raise ToolError("User lookup is ambiguous" if m else "User not found")
    if name == "get_order_details":
        return _order(db, a)
    if name == "get_product_details":
        return _get(db["products"], a["product_id"] if "product_id" in a else None, "Product not found")
    if name == "get_item_details":
        k = arg(a, "item_id")
        for p in db["products"].values():
            if k in p["variants"]:
                return p["variants"][k]
        raise ToolError("Item not found")
    if name == "get_user_details":
        return _user(db, a["user_id"] if "user_id" in a else None)
    if name == "list_all_product_types":
        return dict(sorted(((p["name"], p["product_id"]) for p in db["products"].values()), key=lambda kv: kv[0]))
    if name == "modify_pending_order_address":
        o = _order(db, a)
        if "pending" not in o["status"]:
            raise ToolError("Non-pending order cannot be modified")
        o["address"] = _address_of(a)
        return o
    if name == "modify_pending_order_items":
        o = _order(db, a)
        if o["status"] != "pending":
            raise ToolError("Non-pending order cannot be modified")
        ids = _str_list(a.get("item_ids"), "item_ids")
        nids = _str_list(a.get("new_item_ids"), "new_item_ids")
        diff, last = _swap_diff(db, o, ids, nids, lambda i: f"{i} not found", True)
        pm = _payment(db, o["user_id"], a.get("payment_method_id") if "payment_method_id" in a else None)
        if pm["source"] == "gift_card" and (pm.get("balance") or 0) < diff:
            raise ToolError("Insufficient gift card balance to pay for the new item")
        o["payment_history"].append({"transaction_type": "payment" if diff > 0 else "refund", "amount": abs(diff), "payment_method_id": arg(a, "payment_method_id")})
        if pm["source"] == "gift_card":
            pm["balance"] = _round2((pm.get("balance") or 0) - diff)
        for k in range(len(ids)):
            item = next((i for i in o["items"] if i["item_id"] == ids[k]), None)
            if not item:
                raise ToolError(f"Item {ids[k]} not found")
            # tau2 quirk kept for fidelity: price and options come from the last variant looked up
            item["item_id"] = nids[k]
            item["price"] = last["price"]
            item["options"] = last["options"]
        o["status"] = "pending (item modified)"
        return o
    if name == "modify_pending_order_payment":
        o = _order(db, a)
        if "pending" not in o["status"]:
            raise ToolError("Non-pending order cannot be modified")
        pm = _payment(db, o["user_id"], a.get("payment_method_id") if "payment_method_id" in a else None)
        ph = o["payment_history"]
        if len(ph) != 1 or ph[0]["transaction_type"] != "payment":
            raise ToolError("There should be exactly one payment for a pending order")
        if ph[0]["payment_method_id"] == arg(a, "payment_method_id"):
            raise ToolError("The new payment method should be different from the current one")
        amount = ph[0]["amount"]
        if pm["source"] == "gift_card" and (pm.get("balance") or 0) < amount:
            raise ToolError("Insufficient gift card balance to pay for the order")
        ph.extend([{"transaction_type": "payment", "amount": amount, "payment_method_id": arg(a, "payment_method_id")},
                   {"transaction_type": "refund", "amount": amount, "payment_method_id": ph[0]["payment_method_id"]}])
        if pm["source"] == "gift_card":
            pm["balance"] = _round2((pm.get("balance") or 0) - amount)
        old = _payment(db, o["user_id"], ph[0]["payment_method_id"])
        if old["source"] == "gift_card":
            old["balance"] = _round2((old.get("balance") or 0) + amount)
        return o
    if name == "modify_user_address":
        u = _user(db, a["user_id"] if "user_id" in a else None)
        u["address"] = _address_of(a)
        return u
    if name == "return_delivered_order_items":
        o = _order(db, a)
        if o["status"] != "delivered":
            raise ToolError("Non-delivered order cannot be returned")
        _user(db, o["user_id"])
        pm = _payment(db, o["user_id"], a.get("payment_method_id") if "payment_method_id" in a else None)
        if pm["source"] != "gift_card" and arg(a, "payment_method_id") != o["payment_history"][0]["payment_method_id"]:
            raise ToolError("Payment method should be the original payment method")
        ids = _str_list(a.get("item_ids"), "item_ids")
        all_ids = [i["item_id"] for i in o["items"]]
        for i in ids:
            if ids.count(i) > all_ids.count(i):
                raise ToolError("Some item not found")
        o["status"] = "return requested"
        o["return_items"] = sorted(ids)
        o["return_payment_method_id"] = arg(a, "payment_method_id")
        return o
    if name == "transfer_to_human_agents":
        return "Transfer successful"
    raise ToolError(f"Unknown tool {name}")


def retail_target_user(db: dict, tool: str, a: dict) -> str | None:
    """The customer account a write acts on (None if it cannot be resolved; the tool will then fail anyway)."""
    if tool == "modify_user_address":
        k = arg(a, "user_id")
        return k if k in db["users"] else None
    o = db["orders"].get(arg(a, "order_id"))
    return o["user_id"] if o else None
