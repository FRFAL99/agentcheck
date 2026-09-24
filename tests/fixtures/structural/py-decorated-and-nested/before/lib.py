import functools
from typing import TYPE_CHECKING

@functools.cache
def cached(a):
    def inner(z):
        pass
    return a

if TYPE_CHECKING:
    def only_for_types(a):
        pass
