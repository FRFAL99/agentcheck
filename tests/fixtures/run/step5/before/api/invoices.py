def create_invoice(customer: str, amount: float) -> dict:
    return {"customer": customer, "amount": amount}


def void_invoice(invoice_id: int) -> None:
    pass
