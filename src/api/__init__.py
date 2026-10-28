"""Flask blueprints split out of app.py. Each exposes ``create_blueprint``
taking the app-level dependencies it needs, so the modules stay importable
without the monolith."""
