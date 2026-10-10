"""pywebview window."""
import webview

from .api import Api
from .paths import resource_path


def run(debug: bool = False) -> None:
    api = Api()
    window = webview.create_window(
        "ClusterSound", url=str(resource_path("ui/index.html")), js_api=api,
        width=1480, height=920, min_size=(1000, 640), background_color="#101216")
    api._set_window(window)
    webview.start(http_server=True, debug=debug)
