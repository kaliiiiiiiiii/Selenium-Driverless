Request-Interception
====================

Example Script
~~~~~~~~~~~~~~

.. literalinclude:: files/request_interception.py
  :language: Python

API
~~~

.. autoclass:: selenium_driverless.scripts.network_interceptor.NetworkInterceptor
    :members:
    :special-members: __init__, __aiter__

.. autoclass:: selenium_driverless.scripts.network_interceptor.InterceptedRequest
    :members:
    :special-members: __init__, __aiter__

.. autoclass:: selenium_driverless.scripts.network_interceptor.InterceptedAuth
    :members:
    :special-members: __init__, __aiter__