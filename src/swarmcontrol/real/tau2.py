"""tau2-bench airline domain (Sierra Research, MIT), ported from tau2/domains/airline/tools.py.

Data (db.json, tasks.json, policy.md) is used unmodified from scenarios/sources/tau2-airline. Grading follows tau2's
DB + COMMUNICATE reward: the final database must equal the database produced by replaying the task's gold actions,
and every required piece of information must appear (substring match, commas removed) in an agent message."""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from typing import Any

from ..paths import SCENARIOS
from .jsutil import dumps, js_round, same_db, js_str, num, py_float

DIR = SCENARIOS / "sources" / "tau2-airline"

_DB_TEXT: str | None = None


def fresh_db() -> dict:
    global _DB_TEXT
    if _DB_TEXT is None:
        _DB_TEXT = (DIR / "db.json").read_text()
    return json.loads(_DB_TEXT)


TAU2_TASKS: list[dict] = json.loads((DIR / "tasks.json").read_text())
AIRLINE_POLICY = (DIR / "policy.md").read_text()

# tau2 llm_agent.py system prompt
AGENT_SYSTEM = f"""<instructions>
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy. Always make sure you generate valid JSON only.
</instructions>
<policy>
{AIRLINE_POLICY.strip()}
</policy>"""

FIRST_AGENT_MESSAGE = "Hi! How can I help you today?"


def user_system(t: dict) -> str:
    """tau2 text user-simulator guidelines (default persona) plus the task scenario."""
    i = t["user_scenario"]["instructions"]

    def tab(s: str) -> str:
        return "\n".join(f"\t{l}" for l in s.split("\n"))

    parts = [f"Domain: {i['domain']}", f"Reason for call:\n{tab(i['reason_for_call'])}",
             f"Known info:\n{tab(i['known_info'])}" if i.get("known_info") else "",
             f"Unknown info:\n{tab(i['unknown_info'])}" if i.get("unknown_info") else "",
             f"Task instructions:\n{tab(i['task_instructions'])}"]
    scenario = "\n".join(p for p in parts if p)
    return f"""# User Simulation Guidelines
You are playing the role of a customer contacting a customer service representative.
Your goal is to simulate realistic customer interactions while following specific scenario instructions.

## Core Principles
- Generate one message at a time, maintaining natural conversation flow.
- Strictly follow the scenario instructions you have received.
- When providing addresses or other multi-part entity values from the task, preserve the order of their components exactly as given; do not rearrange them to match local conventions unless the task explicitly instructs a different order.
- Never make up or hallucinate information not provided in the scenario instructions. Information that is not provided in the scenario instructions should be considered unknown or unavailable.
- Avoid repeating the exact instructions verbatim. Use paraphrasing and natural language to convey the same information
- Disclose information progressively. Wait for the agent to ask for specific information before providing it.

## Task Completion
- The goal is to continue the conversation until the task is complete.
- If the instruction goal is satisified, generate the '###STOP###' token to end the conversation.
- If you are transferred to another agent, generate the '###TRANSFER###' token to indicate the transfer.
- If you find yourself in a situation in which the scenario does not provide enough information for you to continue the conversation, generate the '###OUT-OF-SCOPE###' token to end the conversation.
Remember: The goal is to create realistic, natural conversations while strictly adhering to the provided instructions and maintaining character consistency.

<scenario>
{scenario}
</scenario>"""


USER_STOP = re.compile(r"###(STOP|TRANSFER|OUT-OF-SCOPE)###")


def obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def string(description: str) -> dict:
    return {"type": "string", "description": description}


_flight_info = {"type": "object", "properties": {"flight_number": string("Flight number, such as 'HAT001'."),
                                                 "date": string("The date for the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.")},
                "required": ["flight_number", "date"]}
_passenger = {"type": "object", "properties": {"first_name": string("First name."), "last_name": string("Last name."),
                                               "dob": string("Date of birth in the format 'YYYY-MM-DD'.")}, "required": ["first_name", "last_name", "dob"]}
_cabin = {"type": "string", "enum": ["basic_economy", "economy", "business"]}
_pay_id = string("The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.")

AIRLINE_TOOLS = [
    {"name": "book_reservation", "description": "Book a reservation.", "input_schema": obj({
        "user_id": string("The ID of the user to book the reservation such as 'sara_doe_496'."), "origin": string("The IATA code for the origin city such as 'SFO'."),
        "destination": string("The IATA code for the destination city such as 'JFK'."),
        "flight_type": {"type": "string", "enum": ["one_way", "round_trip"]}, "cabin": _cabin,
        "flights": {"type": "array", "items": _flight_info, "description": "An array of objects containing details about each piece of flight."},
        "passengers": {"type": "array", "items": _passenger, "description": "An array of objects containing details about each passenger."},
        "payment_methods": {"type": "array", "items": {"type": "object", "properties": {
            "payment_id": string("The payment id stored in user profile, such as 'credit_card_7815826'."), "amount": {"type": "number"}},
            "required": ["payment_id", "amount"]}, "description": "An array of objects containing details about each payment method."},
        "total_baggages": {"type": "integer", "description": "The total number of baggage items to book the reservation."},
        "nonfree_baggages": {"type": "integer", "description": "The number of non-free baggage items to book the reservation."},
        "insurance": {"type": "string", "enum": ["yes", "no"]},
    }, ["user_id", "origin", "destination", "flight_type", "cabin", "flights", "passengers", "payment_methods", "total_baggages", "nonfree_baggages", "insurance"])},
    {"name": "calculate", "description": "Calculate the result of a mathematical expression, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.",
     "input_schema": obj({"expression": string("The mathematical expression.")}, ["expression"])},
    {"name": "cancel_reservation", "description": "Cancel the whole reservation.", "input_schema": obj({"reservation_id": string("The reservation ID, such as 'ZFA04Y'.")}, ["reservation_id"])},
    {"name": "get_reservation_details", "description": "Get the details of a reservation.", "input_schema": obj({"reservation_id": string("The reservation ID, such as '8JX2WO'.")}, ["reservation_id"])},
    {"name": "get_user_details", "description": "Get the details of a user, including their reservations.", "input_schema": obj({"user_id": string("The user ID, such as 'sara_doe_496'.")}, ["user_id"])},
    {"name": "list_all_airports", "description": "Returns a list of all available airports.", "input_schema": obj({}, [])},
    {"name": "search_direct_flight", "description": "Search for direct flights between two cities on a specific date.", "input_schema": obj({
        "origin": string("The origin city airport in three letters, such as 'JFK'."), "destination": string("The destination city airport in three letters, such as 'LAX'."),
        "date": string("The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.")}, ["origin", "destination", "date"])},
    {"name": "search_onestop_flight", "description": "Search for one-stop flights between two cities on a specific date.", "input_schema": obj({
        "origin": string("The origin city airport in three letters, such as 'JFK'."), "destination": string("The destination city airport in three letters, such as 'LAX'."),
        "date": string("The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.")}, ["origin", "destination", "date"])},
    {"name": "send_certificate", "description": "Send a certificate to a user. Be careful!", "input_schema": obj({
        "user_id": string("The ID of the user, such as 'sara_doe_496'."), "amount": {"type": "integer", "description": "The amount of the certificate to send."}}, ["user_id", "amount"])},
    {"name": "transfer_to_human_agents", "description": "Transfer the user to a human agent, with a summary of the user's issue. Only transfer if the user explicitly asks for a human agent, or given the policy and the available tools, you cannot solve the user's issue.",
     "input_schema": obj({"summary": string("A summary of the user's issue.")}, ["summary"])},
    {"name": "update_reservation_baggages", "description": "Update the baggage information of a reservation.", "input_schema": obj({
        "reservation_id": string("The reservation ID, such as 'ZFA04Y'."),
        "total_baggages": {"type": "integer", "description": "The updated total number of baggage items included in the reservation."},
        "nonfree_baggages": {"type": "integer", "description": "The updated number of non-free baggage items included in the reservation."},
        "payment_id": _pay_id}, ["reservation_id", "total_baggages", "nonfree_baggages", "payment_id"])},
    {"name": "update_reservation_flights", "description": "Update the flight information of a reservation.", "input_schema": obj({
        "reservation_id": string("The reservation ID, such as 'ZFA04Y'."), "cabin": _cabin,
        "flights": {"type": "array", "items": _flight_info, "description": "An array of objects containing details about each piece of flight in the ENTIRE new reservation. Even if the a flight segment is not changed, it should still be included in the array."},
        "payment_id": _pay_id}, ["reservation_id", "cabin", "flights", "payment_id"])},
    {"name": "update_reservation_passengers", "description": "Update the passenger information of a reservation.", "input_schema": obj({
        "reservation_id": string("The reservation ID, such as 'ZFA04Y'."),
        "passengers": {"type": "array", "items": _passenger, "description": "An array of objects containing details about each passenger."}}, ["reservation_id", "passengers"])},
    {"name": "get_flight_status", "description": "Get the status of a flight.", "input_schema": obj({"flight_number": string("The flight number."), "date": string("The date of the flight.")}, ["flight_number", "date"])},
]

WRITE_TOOLS = {"book_reservation", "cancel_reservation", "send_certificate", "update_reservation_baggages", "update_reservation_flights", "update_reservation_passengers"}


class ToolError(Exception):
    """A tool refused the call (tau2 raises; the agent sees the message)."""


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.category(c).startswith("M")).lower()


def arg(a: dict, k: str) -> str:
    """String(a[k]), with JavaScript's 'undefined' for a missing key."""
    return js_str(a[k]) if k in a else "undefined"


def numarg(a: dict, k: str) -> float:
    """Number(a[k]), NaN for a missing key."""
    return num(a[k]) if k in a else float("nan")


def str_or_empty(v: Any) -> str:
    return "" if v is None else js_str(v)


def resolve_key(m: dict, key: Any, what: str) -> str:
    k = str_or_empty(key)
    if k in m:
        return k
    if k.strip() in m:
        return k.strip()
    matches = [c for c in m if fold(c) == fold(k.strip())]
    if len(matches) == 1:
        return matches[0]
    raise ToolError(f"{what} {k} not found")


NOW = "2024-05-15T15:00:00"


def one_of(v: Any, xs: tuple[str, ...], what: str) -> str:
    if v not in xs or not isinstance(v, str):
        raise ToolError(f"Invalid {what}: {dumps(v)}")
    return v


def _field(f: Any, k: str) -> str:
    return str_or_empty(f.get(k)) if isinstance(f, dict) else ""


def flight_infos(v: Any) -> list[dict]:
    if not isinstance(v, list):
        raise ToolError("flights must be an array")
    return [{"flight_number": _field(f, "flight_number"), "date": _field(f, "date")} for f in v]


def passengers(v: Any) -> list[dict]:
    if not isinstance(v, list):
        raise ToolError("passengers must be an array")
    out = []
    for p in v:
        if not isinstance(p, dict) or not p.get("first_name") or not p.get("last_name") or not p.get("dob"):
            raise ToolError("Each passenger needs first_name, last_name and dob")
        out.append({"first_name": js_str(p["first_name"]), "last_name": js_str(p["last_name"]), "dob": js_str(p["dob"])})
    return out


def flight_instance(db: dict, number: str, date: str) -> tuple[dict, dict]:
    f = db["flights"][resolve_key(db["flights"], number, "Flight")]
    if date not in f["dates"]:
        raise ToolError(f"Flight {number} not found on date {date}")
    return f, f["dates"][date]


def search_direct(db: dict, date: str, origin: str | None, destination: str | None, leave_after: str | None = None) -> list[dict]:
    out = []
    for f in db["flights"].values():
        d = f["dates"].get(date)
        if ((origin is None or f["origin"] == origin) and (destination is None or f["destination"] == destination) and d and d["status"] == "available"
                and (leave_after is None or f["scheduled_departure_time_est"] >= leave_after)):
            out.append({"flight_number": f["flight_number"], "origin": f["origin"], "destination": f["destination"], "status": "available",
                        "scheduled_departure_time_est": f["scheduled_departure_time_est"], "scheduled_arrival_time_est": f["scheduled_arrival_time_est"],
                        "date": None, "available_seats": d.get("available_seats"), "prices": d.get("prices")})
    return out


def payment_for_update(user: dict, payment_id: str, total: float) -> dict | None:
    if payment_id not in user["payment_methods"]:
        raise ToolError("Payment method not found")
    pm = user["payment_methods"][payment_id]
    if pm["source"] == "certificate":
        raise ToolError("Certificate cannot be used to update reservation")
    if pm["source"] == "gift_card" and (pm.get("amount") or 0) < total:
        raise ToolError("Gift card balance is not enough")
    if pm["source"] == "gift_card":
        pm["amount"] = (pm.get("amount") or 0) - total
    return {"payment_id": payment_id, "amount": total} if total != 0 else None


AIRPORTS = [("SFO", "San Francisco"), ("JFK", "New York"), ("LAX", "Los Angeles"), ("ORD", "Chicago"), ("DFW", "Dallas"), ("DEN", "Denver"),
            ("SEA", "Seattle"), ("ATL", "Atlanta"), ("MIA", "Miami"), ("BOS", "Boston"), ("PHX", "Phoenix"), ("IAH", "Houston"),
            ("LAS", "Las Vegas"), ("MCO", "Orlando"), ("EWR", "Newark"), ("CLT", "Charlotte"), ("MSP", "Minneapolis"), ("DTW", "Detroit"),
            ("PHL", "Philadelphia"), ("LGA", "LaGuardia")]

# tau2 has three ids (HATHAT..HATHAV); later ones only matter on a shared shift database
_RES_IDS = ["HATHAT", "HATHAU", "HATHAV", *(f"HATHA{c}" for c in "WXYZ"), *(f"HATHB{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")]


def calculate(a: dict) -> str:
    """tau2's calculate: digits, + - * / ( ) . and spaces only; the result is rounded to 2 places and printed as a Python float."""
    e = str_or_empty(a.get("expression"))
    if not all(ch in "0123456789+-*/(). " for ch in e):
        raise ToolError("Invalid characters in expression")
    try:
        v = eval(e, {"__builtins__": {}}, {})  # noqa: S307 - the character check above leaves arithmetic only
    except ZeroDivisionError:
        raise ToolError("division by zero")
    except Exception as err:
        raise ToolError(str(err))
    return py_float(js_round(float(v) * 100) / 100)


def run_airline_tool(db: dict, name: str, a: dict) -> Any:
    """Execute one airline tool against `db` (mutating it), returning the tool's result. Raises ToolError on tool errors, as tau2 does."""
    if name == "book_reservation":
        flights = flight_infos(a.get("flights"))
        pax = passengers(a.get("passengers"))
        pays = [{"payment_id": _field(p, "payment_id"), "amount": num(p.get("amount")) if isinstance(p, dict) and "amount" in p else float("nan")}
                for p in (a["payment_methods"] if isinstance(a.get("payment_methods"), list) else [])]
        c = one_of(a.get("cabin"), ("basic_economy", "economy", "business"), "cabin")
        user = db["users"][resolve_key(db["users"], a.get("user_id"), "User")]
        rid = next((x for x in _RES_IDS if x not in db["reservations"]), None)
        if not rid:
            raise ToolError("Too many reservations")
        res = {
            "reservation_id": rid, "user_id": user["user_id"], "origin": arg(a, "origin"), "destination": arg(a, "destination"),
            "flight_type": one_of(a.get("flight_type"), ("one_way", "round_trip"), "flight_type"),
            "cabin": c, "flights": [], "passengers": copy.deepcopy(pax), "payment_history": copy.deepcopy(pays), "created_at": NOW,
            "total_baggages": numarg(a, "total_baggages"), "nonfree_baggages": numarg(a, "nonfree_baggages"),
            "insurance": one_of(a.get("insurance"), ("yes", "no"), "insurance"),
        }
        total = 0
        insts = []
        for fi in flights:
            flight, inst = flight_instance(db, fi["flight_number"], fi["date"])
            if inst["status"] != "available":
                raise ToolError(f"Flight {flight['flight_number']} not available on date {fi['date']}")
            if inst["available_seats"][c] < len(pax):
                raise ToolError(f"Not enough seats on flight {flight['flight_number']}")
            price = inst["prices"][c]
            res["flights"].append({"origin": flight["origin"], "destination": flight["destination"], "flight_number": flight["flight_number"], "date": fi["date"], "price": price})
            insts.append(inst)
            total += price * len(pax)
        if res["insurance"] == "yes":
            total += 30 * len(pax)
        total += 50 * res["nonfree_baggages"]
        for p in pays:
            if p["payment_id"] not in user["payment_methods"]:
                raise ToolError(f"Payment method {p['payment_id']} not found")
            pm = user["payment_methods"][p["payment_id"]]
            if pm["source"] in ("gift_card", "certificate") and (pm.get("amount") or 0) < p["amount"]:
                raise ToolError(f"Not enough balance in payment method {p['payment_id']}")
        paid = 0
        for p in pays:
            paid += p["amount"]
        if paid != total:
            raise ToolError(f"Payment amount does not add up, total price is {js_str(total)}, but paid {js_str(paid)}")
        for p in pays:
            pm = user["payment_methods"][p["payment_id"]]
            if pm["source"] == "gift_card":
                pm["amount"] = (pm.get("amount") or 0) - p["amount"]
            elif pm["source"] == "certificate":
                del user["payment_methods"][p["payment_id"]]
        for inst in insts:
            inst["available_seats"][c] -= len(pax)
        db["reservations"][rid] = res
        user["reservations"].append(rid)
        return res
    if name == "calculate":
        return calculate(a)
    if name == "cancel_reservation":
        r = db["reservations"][resolve_key(db["reservations"], a.get("reservation_id"), "Reservation")]
        r["payment_history"].extend([{"payment_id": p["payment_id"], "amount": -p["amount"]} for p in r["payment_history"]])
        r["status"] = "cancelled"
        return r
    if name == "get_reservation_details":
        return db["reservations"][resolve_key(db["reservations"], a.get("reservation_id"), "Reservation")]
    if name == "get_user_details":
        return db["users"][resolve_key(db["users"], a.get("user_id"), "User")]
    if name == "list_all_airports":
        return [{"iata": i, "city": c} for i, c in AIRPORTS]
    if name == "search_direct_flight":
        return search_direct(db, arg(a, "date"), arg(a, "origin"), arg(a, "destination"))
    if name == "search_onestop_flight":
        date = arg(a, "date")
        out = []
        for r1 in search_direct(db, date, arg(a, "origin"), None):
            r1["date"] = date
            # tau2 quirk kept for fidelity: the next-day date is not zero-padded
            date2 = f"2024-05-{_parse_int(date[-2:]) + 1}" if "+1" in js_str(r1["scheduled_arrival_time_est"]) else date
            for r2 in search_direct(db, date2, js_str(r1["destination"]), arg(a, "destination"), js_str(r1["scheduled_arrival_time_est"])):
                r2["date"] = date2
                out.append([r1, r2])
        return out
    if name == "send_certificate":
        user = db["users"][resolve_key(db["users"], a.get("user_id"), "User")]
        for pid in (f"certificate_{n}" for n in (3221322, 3221323, 3221324)):
            if pid not in user["payment_methods"]:
                user["payment_methods"][pid] = {"id": pid, "amount": numarg(a, "amount"), "source": "certificate"}
                return f"Certificate {pid} added to user {arg(a, 'user_id')} with amount {arg(a, 'amount')}."
        raise ToolError("Too many certificates")
    if name == "transfer_to_human_agents":
        return "Transfer successful"
    if name == "update_reservation_baggages":
        r = db["reservations"][resolve_key(db["reservations"], a.get("reservation_id"), "Reservation")]
        user = db["users"][resolve_key(db["users"], r["user_id"], "User")]
        total = 50 * max(0, numarg(a, "nonfree_baggages") - r["nonfree_baggages"])
        p = payment_for_update(user, arg(a, "payment_id"), total)
        if p:
            r["payment_history"].append(p)
        r["total_baggages"] = numarg(a, "total_baggages")
        r["nonfree_baggages"] = numarg(a, "nonfree_baggages")
        return r
    if name == "update_reservation_flights":
        flights = flight_infos(a.get("flights"))
        c = one_of(a.get("cabin"), ("basic_economy", "economy", "business"), "cabin")
        r = db["reservations"][resolve_key(db["reservations"], a.get("reservation_id"), "Reservation")]
        user = db["users"][resolve_key(db["users"], r["user_id"], "User")]
        total = 0
        nxt = []
        for fi in flights:
            flight = db["flights"][resolve_key(db["flights"], fi["flight_number"], "Flight")]
            keep = next((x for x in r["flights"] if x["flight_number"] == flight["flight_number"] and x["date"] == fi["date"] and c == r["cabin"]), None)
            if keep:
                total += keep["price"] * len(r["passengers"])
                nxt.append(keep)
                continue
            _, inst = flight_instance(db, flight["flight_number"], fi["date"])
            if inst["status"] != "available":
                raise ToolError(f"Flight {flight['flight_number']} not available on date {fi['date']}")
            if inst["available_seats"][c] < len(r["passengers"]):
                raise ToolError(f"Not enough seats on flight {flight['flight_number']}")
            rf = {"flight_number": flight["flight_number"], "date": fi["date"], "price": inst["prices"][c], "origin": flight["origin"], "destination": flight["destination"]}
            total += rf["price"] * len(r["passengers"])
            nxt.append(rf)
        old = 0
        for f in r["flights"]:
            old += f["price"]
        total -= old * len(r["passengers"])
        p = payment_for_update(user, arg(a, "payment_id"), total)
        if p:
            r["payment_history"].append(p)
        r["flights"] = nxt
        r["cabin"] = c
        return r
    if name == "update_reservation_passengers":
        pax = passengers(a.get("passengers"))
        r = db["reservations"][resolve_key(db["reservations"], a.get("reservation_id"), "Reservation")]
        if len(pax) != len(r["passengers"]):
            raise ToolError("Number of passengers does not match")
        r["passengers"] = copy.deepcopy(pax)
        return r
    if name == "get_flight_status":
        return flight_instance(db, arg(a, "flight_number"), arg(a, "date"))[1]["status"]
    raise ToolError(f"Unknown tool {name}")


def _parse_int(s: str) -> int:
    m = re.match(r"\s*([+-]?\d+)", s)
    return int(m.group(1)) if m else 0


def grade_tau2(t: dict, db: dict, agent_texts: list[str]) -> dict[str, bool]:
    """tau2 reward: DB match against the gold replay, and required information communicated."""
    gold = fresh_db()
    for act in t["evaluation_criteria"].get("actions") or []:
        try:
            run_airline_tool(gold, act["name"], act["arguments"])
        except Exception:
            pass  # tau2 logs and ignores errors in gold actions
    info = t["evaluation_criteria"].get("communicate_info") or []
    return {
        "db_match": same_db(gold, db),
        "info_communicated": all(any(s.lower() in m.lower().replace(",", "") for m in agent_texts) for s in info),
    }


# ---------------------------------------------------------------------------
# Governor checks: deterministic rules taken from the airline policy (policy.md) only.
# They see the request, the database at the time of the call and the customer's last message; never the task's gold actions.

AFFIRM = re.compile(r"\b(yes|yeah|yep|yup|sure|confirm(ed)?|go ahead|proceed|correct|please do|do it|ok(ay)?|that'?s right|sounds good)\b", re.I)


def _flown(db: dict, r: dict) -> bool:
    return any(((db["flights"].get(f["flight_number"]) or {}).get("dates", {}).get(f["date"]) or {}).get("status", "") in ("flying", "landed") for f in r["flights"])


def airline_checks(db: dict, tool: str, a: dict, last_user: str) -> list[dict]:
    out: list[dict] = []

    def add(rule: str, ok: bool, detail: str, source: str) -> None:
        out.append({"rule": rule, "ok": ok, "detail": detail, "source": source})

    def resv() -> dict | None:
        try:
            return db["reservations"][resolve_key(db["reservations"], a.get("reservation_id"), "Reservation")]
        except ToolError:
            return None

    def user_of() -> dict | None:
        try:
            return db["users"][resolve_key(db["users"], a.get("user_id"), "User")]
        except ToolError:
            return None

    if tool in ("book_reservation", "update_reservation_flights", "update_reservation_baggages", "update_reservation_passengers"):
        add("explicit_confirmation", bool(AFFIRM.search(last_user)), "list the action details and obtain the user's explicit confirmation (yes) before updating the booking database",
            "policy: confirmation before database updates")
    if tool == "cancel_reservation":
        r = resv()
        if r:
            statuses = [((db["flights"].get(f["flight_number"]) or {}).get("dates", {}).get(f["date"]) or {}).get("status") for f in r["flights"]]
            eligible = r["created_at"] >= "2024-05-14T15:00:00" or "cancelled" in statuses or r["cabin"] == "business" or r["insurance"] == "yes"
            add("cancellation_not_flown", not _flown(db, r), "a reservation with a flown segment cannot be cancelled by the agent (transfer needed)", "policy: cancel flight")
            add("cancellation_eligible", eligible, "cancellation needs: booked within 24 hours, an airline-cancelled flight, business class, or travel insurance", "policy: cancel flight")
    if tool == "update_reservation_flights":
        r = resv()
        fl = a["flights"] if isinstance(a.get("flights"), list) else []
        if r:
            same = len(fl) == len(r["flights"]) and all(isinstance(f, dict) and f.get("flight_number") == r["flights"][i]["flight_number"] and f.get("date") == r["flights"][i]["date"]
                                                        for i, f in enumerate(fl))
            add("basic_economy_no_flight_change", r["cabin"] != "basic_economy" or same, "basic economy flights cannot be modified", "policy: change flights")
            if a.get("cabin") != r["cabin"]:
                add("no_cabin_change_after_flown", not _flown(db, r), "cabin cannot be changed if any flight in the reservation has already been flown", "policy: change cabin")
            segs = [db["flights"][k] for k in (str_or_empty(f.get("flight_number")) if isinstance(f, dict) else "" for f in fl) if k in db["flights"]]
            if len(segs) == len(fl) and segs:
                if r["flight_type"] == "one_way":
                    ends_ok = segs[0]["origin"] == r["origin"] and segs[-1]["destination"] == r["destination"]
                else:
                    ends_ok = segs[0]["origin"] == r["origin"] and segs[-1]["destination"] == r["origin"] and any(s["destination"] == r["destination"] for s in segs)
                add("same_origin_destination_trip_type", ends_ok, "flights can be changed only without changing the origin, destination and trip type", "policy: change flights")
    if tool == "update_reservation_baggages":
        r = resv()
        if r:
            add("no_bag_removal", numarg(a, "total_baggages") >= r["total_baggages"], "the user can add but not remove checked bags", "policy: change baggage")
    if tool == "book_reservation":
        pax = len(a["passengers"]) if isinstance(a.get("passengers"), list) else 0
        add("max_five_passengers", pax <= 5, "each reservation can have at most five passengers", "policy: book flight")
        user = user_of()
        pays = a["payment_methods"] if isinstance(a.get("payment_methods"), list) else []
        src = [((user or {}).get("payment_methods", {}).get(js_str(p.get("payment_id")) if isinstance(p, dict) and "payment_id" in p else "undefined") or {}).get("source", "unknown")
               for p in pays]
        add("payment_limits", src.count("certificate") <= 1 and src.count("credit_card") <= 1 and src.count("gift_card") <= 3,
            "at most one travel certificate, one credit card and three gift cards per reservation", "policy: book flight")
        if user:
            add("payment_in_profile", "unknown" not in src, "all payment methods must already be in the user profile", "policy: book flight")
    if tool == "send_certificate":
        user = user_of()
        if user:
            rs = [db["reservations"][i] for i in user["reservations"] if i in db["reservations"]]
            eligible = user["membership"] in ("silver", "gold") or any(r["insurance"] == "yes" or r["cabin"] == "business" for r in rs)
            add("compensation_eligible", eligible, "only compensate a silver/gold member, or a user with travel insurance or flying business", "policy: refunds and compensation")
    return out
