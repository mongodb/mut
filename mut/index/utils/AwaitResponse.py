import sys
import time
from concurrent.futures import ThreadPoolExecutor


def wait_for_response(message, function, *args, **kwargs):
    pool = ThreadPoolExecutor(2)
    future = pool.submit(function, *args, **kwargs)
    i = 0
    while not future.done():
        i += 1
        num_dots = 1 + (i % 5)
        sys.stdout.write("\033[K")
        print(message + num_dots*'.', end='\r')
        time.sleep(0.33)
    sys.stdout.write("\033[K")
    return future.result()
