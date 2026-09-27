"""Seed data for the fictional Northwind Gear outdoor store."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    tier TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL,
    placed_at TEXT NOT NULL,
    total REAL NOT NULL,
    items TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shipments (
    order_id TEXT PRIMARY KEY REFERENCES orders(id),
    carrier TEXT NOT NULL,
    tracking TEXT NOT NULL,
    status TEXT NOT NULL,
    promised_date TEXT NOT NULL,
    eta TEXT,
    delivered_at TEXT,
    last_scan TEXT,
    delay_reason TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    order_id TEXT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
"""

CUSTOMERS = [
    ("C-101", "Maya Chen", "maya.chen@example.com", "gold"),
    ("C-102", "Luis Ortega", "luis.ortega@example.com", "standard"),
    ("C-103", "Priya Nair", "priya.nair@example.com", "platinum"),
    ("C-104", "Tom Becker", "tom.becker@example.com", "standard"),
    ("C-105", "Aisha Karim", "aisha.karim@example.com", "gold"),
]

PRODUCTS = [
    ("TNT-2P", "Ridgeline 2P Backpacking Tent", "tents", 289.00),
    ("JKT-RN", "Stormshell Rain Jacket", "apparel", 159.00),
    ("BT-HK", "Summit Mid Hiking Boots", "footwear", 189.00),
    ("SB-20", "Nimbus 20F Sleeping Bag", "sleep", 229.00),
    ("ST-JB", "Pocket Jet Stove", "cooking", 79.00),
    ("HL-400", "Beacon 400 Headlamp", "electronics", 49.00),
    ("PK-45", "Traverse 45L Pack", "packs", 199.00),
]


def _iso(d: date) -> str:
    return d.isoformat()


def _orders(today: date) -> tuple[list[tuple], list[tuple]]:
    d = lambda days: _iso(today + timedelta(days=days))  # noqa: E731
    orders = [
        ("1040", "C-104", "delivered", d(-20), 49.00, [("HL-400", 1)]),
        ("1041", "C-101", "delivered", d(-14), 229.00, [("SB-20", 1)]),
        ("1042", "C-101", "delayed", d(-9), 368.00, [("TNT-2P", 1), ("ST-JB", 1)]),
        ("1043", "C-102", "in_transit", d(-3), 199.00, [("PK-45", 1)]),
        ("1044", "C-103", "processing", d(-1), 189.00, [("BT-HK", 1)]),
        ("1045", "C-102", "delivered", d(-12), 159.00, [("JKT-RN", 1)]),
        ("1046", "C-105", "delivered", d(-45), 189.00, [("BT-HK", 1)]),
        ("1047", "C-103", "delivered", d(-6), 289.00, [("TNT-2P", 1)]),
        ("1048", "C-105", "in_transit", d(-2), 128.00, [("ST-JB", 1), ("HL-400", 1)]),
    ]
    shipments = [
        ("1040", "UPS", "1Z999AA10000001", "delivered", d(-15), None, d(-16), "Delivered, front door", None),
        ("1041", "FedEx", "7700000001", "delivered", d(-9), None, d(-10), "Delivered, reception", None),
        (
            "1042", "UPS", "1Z999AA10000042", "delayed", d(-3), d(2), None,
            "Held at Memphis, TN hub", "Severe weather closed the Memphis regional hub for 48 hours",
        ),
        ("1043", "USPS", "9400100000000043", "in_transit", d(2), d(2), None, "Departed Denver, CO", None),
        ("1044", "UPS", "pending", "label_created", d(4), d(4), None, None, None),
        ("1045", "FedEx", "7700000045", "delivered", d(-7), None, d(-8), "Delivered, mailbox", None),
        ("1046", "UPS", "1Z999AA10000046", "delivered", d(-40), None, d(-41), "Delivered, porch", None),
        ("1047", "FedEx", "7700000047", "delivered", d(-2), None, d(-2), "Delivered, box damaged in transit", None),
        ("1048", "USPS", "9400100000000048", "in_transit", d(3), d(3), None, "Arrived at Chicago, IL facility", None),
    ]
    order_rows = [(o[0], o[1], o[2], o[3], o[4], json.dumps([{"sku": s, "qty": q} for s, q in o[5]]))
                  for o in orders]
    return order_rows, shipments


def seed(conn: sqlite3.Connection, today: date | None = None) -> None:
    today = today or date.today()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
        return
    orders, shipments = _orders(today)
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", CUSTOMERS)
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders)
    conn.executemany("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", shipments)
    conn.commit()
