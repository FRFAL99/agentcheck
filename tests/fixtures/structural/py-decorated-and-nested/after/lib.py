import functools
from typing import TYPE_CHECKING

@functools.cache
def cached(a, b):
    def inner(z, y):
        pass
    return a

if TYPE_CHECKING:
    def only_for_types(a, b):
        pass
