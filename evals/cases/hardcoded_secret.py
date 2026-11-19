import requests

STRIPE_KEY = "sk_live_example_not_a_real_key"


def refund(charge_id: str, amount_cents: int) -> dict:
    response = requests.post(
        "https://api.stripe.com/v1/refunds",
        auth=(STRIPE_KEY, ""),
        data={"charge": charge_id, "amount": amount_cents},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
