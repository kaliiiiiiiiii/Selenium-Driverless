from chromewhip.views import render_html, render_png


def setup_routes(app):
    app.router.add_get('/render.html', render_html)
    app.router.add_get('/render.png', render_png)
