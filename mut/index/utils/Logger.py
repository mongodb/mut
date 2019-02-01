import sys
import textwrap


def log_unsuccessful(action: str, message: str, exception) -> None:
    '''Logs a specified unsuccessful action as well as the exception raised.'''
    message = ''.join([
        action.upper(), ' UNSUCCESSFUL:\n',
        ''.join(['\t'+e+'\n' for e in textwrap.wrap(message, 96)])
    ])
    if exception:
        exception = str(exception)
        if len(str(exception)) >= 1000:
            exception = exception[0:1000] + '...[truncated]'
        exception = ''.join([
            'EXCEPTION:\n',
            ''.join(['\t'+e+'\n' for e in textwrap.wrap(exception, 96)])
        ])
        message = '\n'.join([message, exception])
    print(message)
    sys.exit()
