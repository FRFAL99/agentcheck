import pytest


def test_create():
    assert True


@pytest.mark.skip(reason="flaky")
def test_total():
    assert True


class TestVoid:
    @pytest.mark.xfail
    def test_void(self):
        assert True
