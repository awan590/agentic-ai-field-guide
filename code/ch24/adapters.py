"""Thin adapters between one engagement folder and earlier chapters.

Several earlier modules read their own sample files. These functions
hand them a customer's files instead, without changing a line of
their code: a pilot readout from any week files, a SQLite copy of
exported tables, and business-case inputs built from the customer's
own baseline and pilot.
"""
import contextlib
import csv
import io
import json
import sqlite3
from pathlib import Path

from ch20.pilot_vs_control import to_row
from ch23 import roi_model
from ch23.solution_case import page


def read_json(path):
    return json.loads(Path(path).read_text())


def quiet(fn, *args):
    """Call fn; return its result and everything it printed."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args)
    return result, buf.getvalue()


def load_pilot(folder, names):
    """Chapter 20's rows, read from the customer's week files."""
    rows = []
    for name in names:
        with open(Path(folder) / f"{name}.csv", newline="") as f:
            rows += [to_row(t) for t in csv.DictReader(f)]
    return rows


def open_tables(path):
    """Chapter 19 scans a database, so build one from tables.json."""
    db = sqlite3.connect(":memory:")
    for name, t in read_json(path).items():
        cols = t["columns"]
        db.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        marks = ", ".join("?" for _ in cols)
        db.executemany(f"INSERT INTO {name} VALUES ({marks})",
                       [tuple(r) for r in t["rows"]])
    return db


def roi_inputs(path, base, pilot, changes=()):
    """Chapter 23's inputs, with this customer's baseline and pilot
    in place of the sample's. changes: (key, value) pairs."""
    x = roi_model.inputs(path)
    week = base["all"]["per_week"]
    x.update(tickets_week=week,
             tickets_month=week * roi_model.WEEKS_PER_MONTH,
             handoff=pilot["handoff"]["pilot"],
             pilot_tickets=pilot["tickets"]["pilot"])
    for key, name in (("minutes", "minutes"), ("reopened", "reopen"),
                      ("wrong_refund", "wrong")):
        m = pilot[key]
        x["person_" + name] = m["control"]
        x["agent_" + name] = m["pilot"]
        x["intervals"]["agent_" + name] = (
            max(0.0, m["control"] + m["low"]), m["control"] + m["high"])
    for key, value in changes:
        if key not in x or isinstance(x[key], (str, list, dict)):
            raise ValueError(f"unknown input: {key}")
        x[key] = float(value)
    return x


def case_page(x, customer):
    """Chapter 23's one-page business case, titled for this customer."""
    text = page(x).replace("Example Supply", customer, 1)
    return text.replace("ch17 baseline and the ch20 control group",
                        "this engagement's baseline and control group")
