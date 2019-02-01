import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

_T = TypeVar('_T')


def wait_for_response(message: str, function: Callable[[], _T]) -> _T:
    pool = ThreadPoolExecutor(2)
    future = pool.submit(function)
    i = 0
    while not future.done():
        i += 1
        num_dots = 1 + (i % 5)
        sys.stdout.write("\033[K")
        print(message + num_dots*'.', end='\r')
        time.sleep(0.33)
    sys.stdout.write("\033[K")
    return future.result()
