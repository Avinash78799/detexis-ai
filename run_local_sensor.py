"""Run the Detexis landing app with an opt-in, loopback-only Shield sensor."""

import argparse
import os

from app import create_app, shield_origin


def instrument(api_url, api_key, site_salt):
    from detexis_shield import ShieldWSGIMiddleware

    origin = shield_origin(api_url, loopback_only=True)
    if origin is None:
        raise ValueError("Set SHIELD_URL to the trusted local Shield HTTPS origin")
    if not api_key.strip() or not site_salt.strip():
        raise ValueError("Set SHIELD_API_KEY and SHIELD_SALT for the selected site")
    app = create_app(local_shield_url=origin)
    app.wsgi_app = ShieldWSGIMiddleware(app.wsgi_app, origin, api_key, site_salt,
                                       outage_retry_window=30)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    from waitress import create_server

    try:
        app = instrument(os.getenv("SHIELD_URL", "https://localhost:8443"),
                         os.getenv("SHIELD_API_KEY", ""), os.getenv("SHIELD_SALT", ""))
    except ValueError as error:
        parser.error(str(error))

    try:
        server = create_server(app, host="127.0.0.1", port=args.port, threads=4)
        print(f"Local Detexis entry: http://127.0.0.1:{args.port}", flush=True)
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.wsgi_app.client.close()


if __name__ == "__main__":
    main()
