"""Dev-only: serve the UI in a normal browser, with the Python Api reachable over HTTP.

    python tools/devserver.py [--port 8765]

index.html gets a small shim that defines window.pywebview.api as fetch() calls, so the
exact same app.js runs. Native dialogs are replaced by prompt().
"""
import argparse
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clustersound.api import Api  # noqa: E402

UI = ROOT / "clustersound" / "ui"
SHIM = """<script>
(() => {
  const call = (name) => async (...args) => {
    const r = await fetch('/api/' + name, {method: 'POST', body: JSON.stringify(args)});
    return r.json();
  };
  const names = %s;
  const api = Object.fromEntries(names.map((n) => [n, call(n)]));
  api.pick_folder = async () => prompt('Percorso della cartella da analizzare');
  api.compose_pick_folder = async () => { const p = prompt('Cartella del chord pack'); return p ? call('compose_pick_folder')(p) : call('compose_init')(); };
  api.export_report = async () => { const p = prompt('Salva report in (…/report.csv)'); return p ? call('_dev_export')(p) : null; };
  window.pywebview = { api };
  setTimeout(() => window.dispatchEvent(new Event('pywebviewready')), 0);
})();
</script>"""


class DevApi(Api):
    def _dev_export(self, path):
        from clustersound import export
        export.write(self._lib.items, path)
        return path

    def _save_dialog(self, filename, types):  # no native dialog: save straight into the export folder
        from clustersound.api import EXPORT_DIR
        os.makedirs(EXPORT_DIR, exist_ok=True)
        return os.path.join(EXPORT_DIR, filename)

    def compose_export_versions(self, seqs, pure=False):
        from clustersound.api import EXPORT_DIR
        os.makedirs(EXPORT_DIR, exist_ok=True)
        return self._write_versions(EXPORT_DIR, seqs, pure)


api = DevApi()
METHODS = [m for m in dir(Api) if not m.startswith("_") and callable(getattr(Api, m))]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(UI), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = (UI / "index.html").read_text()
            html = html.replace("<script type=\"module\"", SHIM % json.dumps(METHODS) + "\n<script type=\"module\"")
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        name = self.path.removeprefix("/api/")
        if name not in METHODS and name != "_dev_export":
            self.send_error(404)
            return
        args = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"[]")
        try:
            out = getattr(api, name)(*args)
            body = json.dumps(out).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"error": str(e)}).encode()
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--live-port", type=int, default=0,
                    help="Live bridge port (default: off, so the running app keeps 8770 for the Max for Live device)")
    args = ap.parse_args()
    port = args.port
    print(f"http://localhost:{port}")
    if args.live_port:
        api._live.start(args.live_port)
        print(f"Live bridge: http://127.0.0.1:{args.live_port}/live/ping" if api._live.server else f"Live bridge: {api._live.error}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
