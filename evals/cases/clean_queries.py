import sqlite3


def recent_orders(conn: sqlite3.Connection, customer_id: int, limit: int = 20) -> list[tuple]:
    cursor = conn.execute(
        "SELECT id, total, created_at FROM orders WHERE customer_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (customer_id, limit),
    )
    return cursor.fetchall()


def totals_by_customer(conn: sqlite3.Connection, customer_ids: list[int]) -> dict[int, float]:
    if not customer_ids:
        return {}
    placeholders = ",".join("?" for _ in customer_ids)
    cursor = conn.execute(
        f"SELECT customer_id, SUM(total) FROM orders WHERE customer_id IN ({placeholders}) "
        "GROUP BY customer_id",
        customer_ids,
    )
    return {customer_id: total for customer_id, total in cursor.fetchall()}
