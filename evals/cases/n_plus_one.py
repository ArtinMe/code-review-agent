def order_summaries(db, customer_ids: list[int]) -> list[dict]:
    summaries = []
    for customer_id in customer_ids:
        orders = db.query("SELECT total FROM orders WHERE customer_id = ?", customer_id)
        summaries.append({"customer": customer_id, "total": sum(o["total"] for o in orders)})
    return summaries
