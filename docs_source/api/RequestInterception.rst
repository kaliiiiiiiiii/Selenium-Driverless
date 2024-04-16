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

.. autoclass:: selenium_driverless.scripts.network_interceptor.InterceptedAuth
    :members:

.. autoclass:: selenium_driverless.scripts.network_interceptor.AuthChallenge
    :members:

.. autoclass:: selenium_driverless.scripts.network_interceptor.Request
    :members:

.. autoclass:: selenium_driverless.scripts.network_interceptor.RequestStages
    :members:

.. autoclass:: selenium_driverless.scripts.network_interceptor.RequestPattern
    :members:

.. autoclass:: selenium_driverless.scripts.network_interceptor.AuthAlreadyHandledException
    :members:

.. autoclass:: selenium_driverless.scripts.network_interceptor.RequestDoneException
    :members: