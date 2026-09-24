def create_invoice(customer: str, amount: float, currency: str) -> dict:
    return {"customer": customer, "amount": amount, "currency": currency}
