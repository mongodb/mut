import requests
from requests.exceptions import HTTPError
from mut.index.utils.AwaitResponse import wait_for_response

MARIAN_URL = 'https://marian.mongodb.com/'


def refresh_marian() -> None:
    '''Sends a refresh request to the Marian server.'''
    print("\n### Refreshing Marian\n")
    refresh_url = MARIAN_URL+'refresh'
    try:
        res = wait_for_response(
            'Attempting to refresh Marian',
            lambda: requests.post(refresh_url, data={}))
        res.raise_for_status()
        if res.status_code != 200:
            message = ' '.join(['...but received unexpected response:',
                                str(res.status_code)])
            print(message)
    except ConnectionError as ex:
        raise FailedRefreshError(ex, 'Unable to connect to the Marian Server.')
    except HTTPError as ex:
        raise FailedRefreshError(ex, 'HTTP Error.')


class FailedRefreshError(Exception):
    '''Failed to refresh Marian.'''
    def __init__(self, exception, message: str) -> None:
        super(FailedRefreshError, self).__init__()
