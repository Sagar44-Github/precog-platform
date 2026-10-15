"""Serves the built web app (web/dist) at /app/ from the same Flask app.

Same address as the API, so the login cookie just works and no CORS settings are needed.
"""
from flask import Response, redirect, request, send_from_directory
from werkzeug.security import safe_join

NO_CACHE_FILES = ("index.html", "sw.js", "manifest.webmanifest")
NOT_BUILT_TEXT = (
    "The web app has not been built yet.\n"
    "Open a terminal in the 'web' folder and run:  npm install  then  npm run build\n"
)


def register_webapp(app, config):
    dist = config.web_dist

    def _index():
        if not (dist / "index.html").is_file():
            return Response(NOT_BUILT_TEXT, status=503, mimetype="text/plain")
        return send_from_directory(dist, "index.html")

    @app.route("/app")
    def precog_app_redirect():
        return redirect("/app/", code=302)

    @app.route("/app/")
    def precog_app_index():
        return _index()

    @app.route("/app/<path:path>")
    def precog_app_files(path):
        full = safe_join(str(dist), path)
        if full is not None and (dist / path).is_file():
            return send_from_directory(dist, path)
        last_part = path.rsplit("/", 1)[-1]
        if "." in last_part:
            return Response("Not found", status=404, mimetype="text/plain")
        return _index()  # a page address inside the app: let the app's router handle it

    @app.after_request
    def precog_app_cache_rules(response):
        if request.path.startswith("/app"):
            if request.path in ("/app", "/app/") or request.path.rsplit("/", 1)[-1] in NO_CACHE_FILES:
                response.headers["Cache-Control"] = "no-cache"
        return response
