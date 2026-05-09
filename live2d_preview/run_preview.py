from __future__ import annotations

import functools
import http.server
from pathlib import Path
import socketserver
import threading
import time
import webbrowser


PORT = 8765
ROOT = Path(__file__).resolve().parent


def main() -> int:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{PORT}/index.html"
        print(f"Live2D preview: {url}")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
