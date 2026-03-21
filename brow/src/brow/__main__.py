import sys
from brow.daemon import run_daemon

if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else None
    run_daemon(port=port)
