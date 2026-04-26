import contextlib
from contextlib import AbstractContextManager
import logging
import sys


class permit(AbstractContextManager):
    """Context manager to allow specified exceptions

    The specified exceptions will be allowed to bubble up. Other
    exceptions are suppressed.

    After a non-matching exception is suppressed, execution proceeds
    with the next statement following the with statement.

         with allow(KeyboardInterrupt):
             time.sleep(300)
         # Execution still resumes here if no KeyboardInterrupt
    """

    def __init__(self, *exceptions): self._exceptions = exceptions

    def __enter__(self): pass

    def __exit__(self, exctype, excinst, exctb):
        return exctype is not None and not issubclass(exctype, self._exceptions)
