import pytest


@pytest.mark.asyncio
async def test_get_source(h_driver, test_server):
    url = test_server.url
    target = h_driver.current_target
    await target.get(url)
    source = await target.page_source
    assert source == '<html><head></head><body>Hello World!</body></html>'


@pytest.mark.asyncio
async def test_get_source_with_shadow(h_driver, subtests, test_server):
    url = test_server.url
    target = h_driver.current_target

    await target.get(url)
    await target.execute_script("""
    const host = document.createElement('div');
    document.body.appendChild(host);
    let shadowRoot = host.attachShadow({ mode: 'closed' });
    shadowRoot.innerHTML = `<p>Isolated content</p>`;
    """, unique_context=False)
    source = await target.page_source
    mhtml = await target.snapshot()
    assert '<body>Hello World!<div><template shadowmode=3D"closed"><p>=\r\nIsolated content</p></template></div></body>' in mhtml
    assert source == '<html><head></head><body>Hello World!<div></div></body></html>'
