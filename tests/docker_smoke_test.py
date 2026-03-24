import subprocess, sys, time, os, pathlib, httpx

BROW = [sys.executable, "-m", "brow"]
PORT = 19987
BASE = f"http://127.0.0.1:{PORT}"

def run(*args, timeout=30):
    r = subprocess.run([*BROW, *args], capture_output=True, text=True, timeout=timeout)
    assert r.returncode == 0, f"FAIL: brow {' '.join(args)}\nstdout: {r.stdout}\nstderr: {r.stderr}"
    return r.stdout.strip()

def api_get(path, **kw):
    return httpx.get(f"{BASE}{path}", timeout=10, **kw).json()

def api_post(path, **kw):
    return httpx.post(f"{BASE}{path}", timeout=30, **kw).json()

def api_delete(path):
    return httpx.delete(f"{BASE}{path}", timeout=10).json()

def wait_daemon():
    for _ in range(30):
        try:
            if httpx.get(f"{BASE}/status", timeout=1).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("daemon never started")

print("=== Xvfb check ===")
assert os.environ.get("DISPLAY") == ":99", "DISPLAY not set to :99"
assert pathlib.Path("/tmp/.X11-unix/X99").exists(), "Xvfb socket not found"
print("OK: Xvfb :99 active")

print("\n=== Start daemon ===")
subprocess.Popen(
    [sys.executable, "-m", "brow.daemon"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
wait_daemon()
status = api_get("/status")
print(f"OK: daemon running — {status}")

print("\n=== Create session (headless) ===")
r = api_post("/sessions", json={"profile": "default", "headless": True})
sid = r["id"]
assert sid
print(f"OK: session {sid}")

print("\n=== Navigate to data URI ===")
r = api_post(f"/browser/{sid}/navigate", json={"url": "data:text/html,<h1>Hello Docker</h1>"})
print(f"OK: navigated to {r['url']}")

print("\n=== Snapshot ===")
snap = api_get(f"/browser/{sid}/snapshot")
assert "Hello Docker" in snap["tree"], f"snapshot missing content: {snap['tree'][:200]}"
print("OK: snapshot contains 'Hello Docker'")

print("\n=== Eval JS via page.evaluate ===")
r = api_post(f"/eval/{sid}", json={"code": "result = await page.evaluate('document.querySelector(\"h1\").textContent')"})
print(f"OK: eval returned '{r.get('result')}'")
assert r.get("result") == "Hello Docker", f"unexpected eval result: {r}"

print("\n=== Click h1 ===")
api_post(f"/browser/{sid}/click", json={"selector": "h1"})
print("OK: click worked")

print("\n=== Screenshot ===")
r = api_post(f"/browser/{sid}/screenshot", json={})
assert r.get("path"), f"no screenshot path: {r}"
print(f"OK: screenshot at {r['path']}")

print("\n=== Create headed session (Xvfb) ===")
r2 = api_post("/sessions", json={"profile": "headed-test", "headless": False})
sid2 = r2["id"]
assert sid2
print(f"OK: headed session {sid2}")

api_post(f"/browser/{sid2}/navigate", json={"url": "data:text/html,<h1>Headed</h1>"})
snap2 = api_get(f"/browser/{sid2}/snapshot")
assert "Headed" in snap2["tree"]
print("OK: headed session works via Xvfb")

print("\n=== Cleanup ===")
api_delete(f"/sessions/{sid}")
api_delete(f"/sessions/{sid2}")
print("OK: sessions deleted")

print("\n=== ALL DOCKER SMOKE TESTS PASSED ===")
