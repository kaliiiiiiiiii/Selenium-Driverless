HTTP API
========

This represents what is currently available.

The goal is to match the `splash HTTP API <https://splash.readthedocs.io/en/stable/api.html#splash-http-api>`_
though likely to delay the ``execute`` and ``run`` endpoints till the end until
a decision is made on whether to support lua scripting.

.. _render.html:

render.html
-----------

Return the HTML of the javascript-rendered page.

Arguments:

.. _arg-url:

url : string : required
  The url to render (required)

.. _arg-wait:

wait : float : optional
  Time (in seconds) to wait for updates after page is loaded i.e. the
  relevant ``Page.frameStoppedLoading`` event is received.
  (defaults to 0). Increase this value if you expect pages to contain
  setInterval/setTimeout javascript calls, because with wait=0
  callbacks of setInterval/setTimeout won't be executed. Non-zero
  :ref:`wait <arg-wait>` is also required for PNG and JPEG rendering when
  doing full-page rendering (see :ref:`render_all <arg-render-all>`).

  Wait time must be less than :ref:`timeout <arg-timeout>`.

.. TODO: implement
   .. _arg-baseurl:

   baseurl : string : optional
     The base url to render the page with.

     Base HTML content will be feched from the URL given in the url
     argument, while relative referenced resources in the HTML-text used to
     render the page are fetched using the URL given in the baseurl argument
     as base. See also: :ref:`render-html-doesnt-work`.

   .. _arg-timeout:

   timeout : float : optional
     A timeout (in seconds) for the render (defaults to 30).

     By default, maximum allowed value for the timeout is 90 seconds.
     To override it start Splash with ``--max-timeout`` command line option.
     For example, here Splash is configured to allow timeouts up to 5 minutes::

         $ docker run -it -p 8050:8050 scrapinghub/splash --max-timeout 300

   .. _arg-resource-timeout:

   resource_timeout : float : optional
     A timeout (in seconds) for individual network requests.

     See also: :ref:`splash-on-request` and its
     ``request:set_timeout(timeout)`` method; :ref:`splash-resource-timeout`
     attribute.

   .. _arg-proxy:

   proxy : string : optional
     Proxy profile name or proxy URL. See :ref:`Proxy Profiles`.

     A proxy URL should have the following format:
     ``[protocol://][user:password@]proxyhost[:port])``

     Where protocol is either ``http`` or ``socks5``. If port is not specified,
     the port 1080 is used by default.

.. _arg-js:

js : string : optional
  Javascript profile name. See :ref:`Javascript Profiles`.

.. _arg-js-source:

js_source : string : optional
    JavaScript code to be executed in page context.
    See :ref:`execute javascript`.

.. _arg-filters:

filters : string : optional
  Comma-separated list of request filter names. See `Request Filters`_

.. _arg-allowed-domains:

allowed_domains : string : optional
  Comma-separated list of allowed domain names.
  If present, Splash won't load anything neither from domains
  not in this list nor from subdomains of domains not in this list.

.. _arg-allowed-content-types:

allowed_content_types : string : optional
  Comma-separated list of allowed content types.
  If present, Splash will abort any request if the response's content type
  doesn't match any of the content types in this list.
  Wildcards are supported using the `fnmatch <https://docs.python.org/3/library/fnmatch.html>`_
  syntax.

.. _arg-forbidden-content-types:

forbidden_content_types : string : optional
  Comma-separated list of forbidden content types.
  If present, Splash will abort any request if the response's content type
  matches any of the content types in this list.
  Wildcards are supported using the `fnmatch <https://docs.python.org/3/library/fnmatch.html>`_
  syntax.

.. _arg-viewport:

viewport : string : optional
  View width and height (in pixels) of the browser viewport to render the web
  page. Format is "<width>x<height>", e.g. 800x600.  Default value is 1024x768.

  'viewport' parameter is more important for PNG and JPEG rendering; it is supported for
  all rendering endpoints because javascript code execution can depend on
  viewport size.

  For backward compatibility reasons, it also accepts 'full' as value;
  ``viewport=full`` is semantically equivalent to ``render_all=1`` (see
  :ref:`render_all <arg-render-all>`).

.. _arg-images:

images : integer : optional
    Whether to download images. Possible values are
    ``1`` (download images) and ``0`` (don't download images). Default is 1.

    Note that cached images may be displayed even if this parameter is 0.
    You can also use `Request Filters`_ to strip unwanted contents based on URL.

.. _arg-headers:

headers : JSON array or object : optional
    HTTP headers to set for the first outgoing request.

    This option is only supported for ``application/json`` POST requests.
    Value could be either a JSON array with ``(header_name, header_value)``
    pairs or a JSON object with header names as keys and header values
    as values.

    "User-Agent" header is special: is is used for all outgoing requests,
    unlike other headers.

.. _arg-body:

body : string : optional
    Body of HTTP POST request to be sent if method is POST.
    Default ``content-type`` header for POST requests is ``application/x-www-form-urlencoded``.

.. _arg-http-method:

http_method : string : optional
    HTTP method of outgoing Splash request. Default method is GET. Splash also
    supports POST.

.. _arg-save-args:

save_args : JSON array or a comma-separated string : optional
    A list of argument names to put in cache. Splash will store each
    argument value in an internal cache and return ``X-Splash-Saved-Arguments``
    HTTP header with a list of SHA1 hashes for each argument
    (a semicolon-separated list of name=hash pairs)::

        name1=9a6747fc6259aa374ab4e1bb03074b6ec672cf99;name2=ba001160ef96fe2a3f938fea9e6762e204a562b3

    Client can then use :ref:`load_args <arg-load-args>` parameter
    to pass these hashes instead of argument values. This is most useful
    when argument value is large and doesn't change often
    (:ref:`js_source <arg-js-source>` or :ref:`lua_source <arg-lua-source>`
    are often good candidates).

.. _arg-load-args:

load_args : JSON object or a string : optional
    Parameter values to load from cache.
    ``load_args`` should be either ``{"name": "<SHA1 hash>", ...}``
    JSON object or a raw ``X-Splash-Saved-Arguments`` header value
    (a semicolon-separated list of name=hash pairs).

    For each parameter in ``load_args`` Splash tries to fetch the
    value from the internal cache using a provided SHA1 hash as a key.
    If all values are in cache then Splash uses them as argument values
    and then handles the request as usual.

    If at least on argument can't be found Splash returns **HTTP 498** status
    code. In this case client should repeat the request, but
    use :ref:`save_args <arg-save-args>` and send full argument values.

    :ref:`load_args <arg-load-args>` and :ref:`save_args <arg-save-args>`
    allow to save network traffic by not sending large arguments with each
    request (:ref:`js_source <arg-js-source>` and
    :ref:`lua_source <arg-lua-source>` are often good candidates).

    Splash uses LRU cache to store values; the number of entries is limited,
    and cache is cleared after each Splash restart. In other words, storage
    is not persistent; client should be ready to re-send the arguments.

Examples
~~~~~~~~

Curl example::

    curl 'http://localhost:8050/render.html?url=http://domain.com/page-with-javascript.html&timeout=10&wait=0.5'

The result is always encoded to utf-8. Always decode HTML data returned
by render.html endpoint from utf-8 even if there are tags like

::

   <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">

in the result.

.. _render.png:

render.png
----------

Return a image (in PNG format) of the javascript-rendered page.

Arguments:

Same as `render.html`_ plus the following ones:

.. _arg-width:

width : integer : optional
  Resize the rendered image to the given width (in pixels) keeping the aspect
  ratio.

.. _arg-height:

height : integer : optional
  Crop the renderd image to the given height (in pixels). Often used in
  conjunction with the width argument to generate fixed-size thumbnails.

.. _arg-render-all:

render_all : int : optional
  Possible values are ``1`` and ``0``.  When ``render_all=1``, extend the
  viewport to include the whole webpage (possibly very tall) before rendering.
  Default is ``render_all=0``.

  .. note::

      ``render_all=1`` requires non-zero :ref:`wait <arg-wait>` parameter. This is an
      unfortunate restriction, but it seems that this is the only way to make
      rendering work reliably with ``render_all=1``.

.. _arg-scale-method:

scale_method : string : optional
  Possible values are ``raster`` (default) and ``vector``.  If
  ``scale_method=raster``, rescaling operation performed via :ref:`width
  <arg-width>` parameter is pixel-wise.  If ``scale_method=vector``, rescaling
  is done element-wise during rendering.

  .. note::

     Vector-based rescaling is more performant and results in crisper fonts and
     sharper element boundaries, however there may be rendering issues, so use
     it with caution.

Examples
~~~~~~~~

Curl examples::

    # render with timeout
    curl 'http://localhost:8050/render.png?url=http://domain.com/page-with-javascript.html&timeout=10'

    # 320x240 thumbnail
    curl 'http://localhost:8050/render.png?url=http://domain.com/page-with-javascript.html&width=320&height=240'


.. _render.jpeg:

render.jpeg
-----------

Return a image (in JPEG format) of the javascript-rendered page.

Arguments:

Same as `render.png`_ plus the following ones:

.. _arg-quality:

quality : integer : optional
  JPEG quality parameter in range from ``0`` to ``100``.
  Default is ``quality=75``.

  .. note::

      ``quality`` values above ``95`` should be avoided;
      ``quality=100`` disables portions of the JPEG compression algorithm,
      and results in large files with hardly any gain in image quality.


Examples
~~~~~~~~

Curl examples::

    # render with default quality
    curl 'http://localhost:8050/render.jpeg?url=http://domain.com/'

    # render with low quality
    curl 'http://localhost:8050/render.jpeg?url=http://domain.com/&quality=30'
