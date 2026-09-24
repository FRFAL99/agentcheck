import pytest

from billing.invoices import total


@pytest.mark.skip
def test_total():
    assert total([1, 2]) == 3
