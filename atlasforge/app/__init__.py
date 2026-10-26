"""Atlas Map Forge app: a local web interface in its own window.

    atlasforge app            (or: atlasforge-app)

Uses pywebview for the window when it is installed (pip install atlas-map-forge[app]); otherwise the
interface opens in the default web browser.
"""
import sys
import time
import webbrowser

from .server import serve


class _JsApi:
    """Functions the page can call through pywebview (window.pywebview.api.*).

    Keep every attribute private (leading underscore): pywebview walks all public attributes of this
    object recursively to build the JavaScript API. A public reference to the window made it walk the
    whole native window object from a background thread, which froze the app on Windows
    ("Not responding")."""

    def __init__(self):
        self._window = None

    def pick_file(self, start=""):
        import webview
        res = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=start or "",
                                             file_types=("Zero-K maps (*.sdz;*.sd7;*.smf)", "All files (*.*)"))
        return res[0] if res else ""

    def pick_project(self, start=""):
        import webview
        res = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=start or "",
                                             file_types=("Forge projects (*.forge.json;*.json)", "All files (*.*)"))
        return res[0] if res else ""

    def pick_folder(self, start=""):
        import webview
        res = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=start or "")
        return res[0] if res else ""


def run(port=0, window=True, quiet=True):
    srv, url, state = serve(port, quiet)
    url_t = url + "?t=" + state.token
    if window:
        try:
            import webview
        except ImportError:
            webview = None
            print("pywebview is not installed, opening the browser instead "
                  "(pip install atlas-map-forge[app] for the app window)")
        if webview is not None:
            api = _JsApi()
            api._window = webview.create_window("Atlas Map Forge", url_t, js_api=api, width=1560, height=980,
                                               min_size=(1100, 720), background_color="#121316")
            webview.start()
            srv.shutdown()
            return 0
    print(f"Atlas Map Forge is running at {url_t}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url_t)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


def selftest():
    """Start the server, make one small preview and fetch its layers. Exit code 0 = everything works.
    Used by the release build to check the packed program."""
    import json
    import urllib.error
    import urllib.request
    srv, url, state = serve(0)
    try:
        def call(path, body=None):
            req = urllib.request.Request(url + "api/" + path, headers={"X-Forge-Token": state.token},
                                         data=json.dumps(body).encode() if body is not None else None)
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    return r.read()
            except urllib.error.HTTPError as ex:
                raise RuntimeError(f"{path}: HTTP {ex.code} {ex.read()[:500]!r}") from None
        info = json.loads(call("state"))
        p = json.loads(call("preview", {"template": "skirmish", "values": {"size": 8}, "seed": 3}))
        for layer in ("relief", "height", "cells", "reach_tanks"):
            call(f"layer/{p['id']}/{layer}")
        with urllib.request.urlopen(url + "index.html") as r:
            page = r.read()
        ok = p["ok"] and b"Atlas Map Forge" in page and len(info["templates"]) >= 6
        built = ""
        if "--build" in sys.argv:                     # full map build: texture workers, compression, archive
            import os
            import tempfile
            from .. import forge
            from ..config import ForgeConfig
            with tempfile.TemporaryDirectory() as tmp:
                t0 = time.time()
                res = forge.build(state.designs[p["id"]].design, outdir=tmp, config=ForgeConfig(author="selftest"),
                                  log=lambda *a: None, preview=False)
                from .. import watermark
                ok = ok and os.path.getsize(res["path"]) > 1_000_000 and watermark.verify(res["path"])["forge"]
                built = f", build {time.time() - t0:.0f} s ({res['bytes'] / 1e6:.1f} MB)"
        print(f"selftest {'OK' if ok else 'FAILED'}: version {info['version']}, {len(info['templates'])} templates, "
              f"preview {p['seconds']} s{built}")
        return 0 if ok else 1
    finally:
        srv.shutdown()


def _log_to_file():
    """A windowed program has no console: send output and errors to a log file next to the settings."""
    import os
    from ..config import config_path
    if sys.stdout is not None and sys.stderr is not None:
        return None
    path = os.environ.get("ATLASFORGE_LOG") or os.path.join(os.path.dirname(config_path()), "app.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path, "w", encoding="utf8", buffering=1)
    sys.stdout = sys.stderr = f
    return path


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    _log_to_file()
    if "--selftest" in sys.argv:
        try:
            code = selftest()
        except Exception:
            import traceback
            traceback.print_exc()
            code = 1
        sys.stdout.flush()
        sys.exit(code)
    sys.exit(run(window="--browser" not in sys.argv))
