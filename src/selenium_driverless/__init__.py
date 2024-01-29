import traceback

# noinspection PyUnresolvedReferences
import cdp_socket
import sys

EXC_HANDLER = (lambda e: traceback.print_exc())
sys.modules["cdp_socket"].EXC_HANDLER = EXC_HANDLER

__version__ = "1.7.2"
