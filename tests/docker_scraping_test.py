import subprocess, sys, time, os, pathlib, threading, json, httpx, uvicorn

PORT_FIXTURE = 18888
PORT_BROW = 19987
BASE = f"http://127.0.0.1:{PORT_BROW}"
FIXTURE = f"http://127.0.0.1:{PORT_FIXTURE}"

def api_get(path, **kw):
    return httpx.get(f"{BASE}{path}", timeout=15, **kw).json()

def api_post(path, **kw):
    return httpx.post(f"{BASE}{path}", timeout=30, **kw).json()

def api_delete(path):
    return httpx.delete(f"{BASE}{path}", timeout=10).json()

def wait_for(url, tries=30):
    for _ in range(tries):
        try:
            if httpx.get(url, timeout=1).status_code in (200, 404):
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"never ready: {url}")

def nav(sid, path):
    return api_post(f"/browser/{sid}/navigate", json={"url": f"{FIXTURE}{path}"})

def snap(sid, **kw):
    return api_get(f"/browser/{sid}/snapshot", params=kw)["tree"]

def click(sid, sel):
    return api_post(f"/browser/{sid}/click", json={"selector": sel})

def fill(sid, sel, val):
    return api_post(f"/browser/{sid}/fill", json={"selector": sel, "value": val})

def js(sid, code):
    escaped = code.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
    py_code = f"result = await page.evaluate('''{escaped}''')"
    return api_post(f"/eval/{sid}", json={"code": py_code})

def wait_sel(sid, sel, timeout=10000):
    return api_post(f"/browser/{sid}/wait", json={"selector": sel, "timeout": timeout})

sys.path.insert(0, "/app/benchmarks")
from fixtures.app import create_fixture_app

print("=== Starting fixture server ===")
fixture_app = create_fixture_app()
t = threading.Thread(target=lambda: uvicorn.run(fixture_app, host="0.0.0.0", port=PORT_FIXTURE, log_level="error"), daemon=True)
t.start()
wait_for(f"http://127.0.0.1:{PORT_FIXTURE}/static/form.html")
print("OK: fixture server up")

print("\n=== Starting brow daemon ===")
subprocess.Popen([sys.executable, "-m", "brow.daemon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
wait_for(f"{BASE}/status")
print("OK: brow daemon up")

r = api_post("/sessions", json={"profile": "test", "headless": True})
sid = r["id"]
print(f"OK: session {sid}")

passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    print(f"\n{'='*50}")
    print(f"TEST: {name}")
    print(f"{'='*50}")
    try:
        fn()
        passed += 1
        print(f"PASS: {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"FAIL: {name} — {e}")


def test_search_extract():
    nav(sid, "/static/search.html")
    tree = snap(sid)
    assert "Search Results" in tree

    r = js(sid, """
        Array.from(document.querySelectorAll('.result')).map(el => ({
            name: el.querySelector('.title').textContent,
            rating: el.querySelector('.rating').textContent
        }))
    """.replace("\n", " "))
    results = r["result"]
    assert len(results) == 7, f"expected 7 results, got {len(results)}"
    assert results[0]["name"] == "Blue Bottle Coffee"
    ratings = [float(x["rating"]) for x in results]
    best = max(results, key=lambda x: float(x["rating"]))
    assert best["name"] == "Devocion", f"expected Devocion as best, got {best['name']}"
    print(f"  Extracted {len(results)} coffee shops, best: {best['name']} ({best['rating']})")

def test_catalog_scrape():
    nav(sid, "/static/catalog.html")
    r = js(sid, """
        Array.from(document.querySelectorAll('.product')).map(el => ({
            name: el.querySelector('.name').textContent,
            price: el.querySelector('.price').textContent,
            category: el.dataset.category,
            rating: el.querySelector('.rating').textContent
        }))
    """.replace("\n", " "))
    products = r["result"]
    assert len(products) == 5
    laptops = [p for p in products if p["category"] == "laptops"]
    phones = [p for p in products if p["category"] == "phones"]
    assert len(laptops) == 3 and len(phones) == 2
    cheapest = min(products, key=lambda p: int(p["price"].replace("$", "").replace(",", "")))
    assert cheapest["name"] == "BudgetPhone SE"
    print(f"  {len(laptops)} laptops, {len(phones)} phones, cheapest: {cheapest['name']} {cheapest['price']}")

def test_form_fill_submit():
    nav(sid, "/static/form.html")
    fill(sid, "#name", "Test User")
    fill(sid, "#email", "test@example.com")
    fill(sid, "#message", "Hello from Docker!")
    api_post(f"/browser/{sid}/click", json={"selector": "#subject", "timeout": 5000})
    r = js(sid, "document.querySelector('#subject').value = 'support'; document.querySelector('#subject').value")
    click(sid, "button[type='submit']")
    time.sleep(1)
    tree = snap(sid)
    assert "Confirmation" in tree, f"form submit failed: {tree[:300]}"
    assert "Test User" in tree
    print(f"  Form submitted, confirmation received")

def test_login_flow():
    nav(sid, "/static/form.html")
    nav(sid, "/login")
    r = js(sid, "document.title || document.URL")
    api_post(f"/browser/{sid}/navigate", json={"url": f"{FIXTURE}/static/form.html"})
    tree = snap(sid)

    nav(sid, "/static/form.html")
    r = api_post(f"/eval/{sid}", json={"code": f"""
import httpx
client = httpx.Client()
resp = client.post('{FIXTURE}/login', data={{'username': 'admin', 'password': 'password123'}}, follow_redirects=True)
result = {{'status': resp.status_code, 'has_cookie': 'auth_token' in resp.cookies, 'body': resp.text[:200]}}
"""})
    assert "Login Successful" in str(r.get("result", r))
    print(f"  Login flow verified via API")

def test_dynamic_content_wait():
    nav(sid, "/dynamic")
    tree = snap(sid)
    assert "Loading" in tree, f"expected loading state: {tree[:200]}"

    wait_sel(sid, "#dynamic-content:not([style*='none'])", timeout=5000)
    time.sleep(2.5)

    r = js(sid, """
        Array.from(document.querySelectorAll('#dynamic-content .item')).map(el => ({
            name: el.querySelector('.name').textContent,
            value: el.querySelector('.value').textContent
        }))
    """.replace("\n", " "))
    items = r["result"]
    assert len(items) == 3
    assert items[0]["name"] == "Alpha" and items[0]["value"] == "100"
    print(f"  Waited for dynamic content, got {len(items)} items: {[i['name'] for i in items]}")

def test_multipage_navigation():
    nav(sid, "/static/multipage/page1.html")
    tree = snap(sid)
    assert "About Us" in tree

    r1 = js(sid, "document.querySelector('.founded').textContent")
    assert "2020" in r1["result"]

    click(sid, "a[href*='page2']")
    time.sleep(0.5)
    tree = snap(sid)
    assert "Our Team" in tree

    r2 = js(sid, """
        Array.from(document.querySelectorAll('.member')).map(el => ({
            name: el.querySelector('.name').textContent,
            role: el.querySelector('.role').textContent
        }))
    """.replace("\n", " "))
    members = r2["result"]
    assert len(members) == 3
    assert members[1]["name"] == "Bob Park"

    click(sid, "a[href*='page3']")
    time.sleep(0.5)
    r3 = js(sid, "document.querySelector('.email').textContent")
    assert "hello@example.com" in r3["result"]
    print(f"  Navigated 3 pages, found {len(members)} team members, contact: {r3['result']}")

def test_multistep_wizard():
    nav(sid, "/static/steps.html")

    fill(sid, "#first-name", "Jane")
    fill(sid, "#last-name", "Doe")
    click(sid, "#next-1")
    time.sleep(0.3)

    fill(sid, "#phone", "555-1234")
    fill(sid, "#city", "San Francisco")
    click(sid, "#next-2")
    time.sleep(0.3)

    click(sid, "#next-3")
    time.sleep(0.3)

    tree = snap(sid)
    assert "Review" in tree
    r = js(sid, "document.getElementById('review-data').textContent")
    assert "Jane Doe" in r["result"]

    click(sid, "#submit-wizard")
    time.sleep(0.3)
    tree = snap(sid)
    assert "Registration Complete" in tree
    print(f"  Completed 4-step wizard, review showed: {r['result']}")

def test_large_page():
    nav(sid, "/large")
    r = js(sid, "document.querySelectorAll('.item').length")
    assert r["result"] == 550, f"expected 550 items, got {r['result']}"

    tree = snap(sid)
    assert "Large Page Test" in tree

    r2 = js(sid, """
        (() => {
            const items = document.querySelectorAll('.item');
            const first = items[0].querySelector('.label').textContent;
            const last = items[items.length-1].querySelector('.label').textContent;
            return {count: items.length, first, last};
        })()
    """.replace("\n", " "))
    data = r2["result"]
    assert data["count"] == 550
    assert data["first"] == "Item 0"
    assert data["last"] == "Item 549"
    print(f"  Large page: {data['count']} items, first={data['first']}, last={data['last']}")

def test_headed_session_scraping():
    r = api_post("/sessions", json={"profile": "headed-scrape", "headless": False})
    sid2 = r["id"]

    api_post(f"/browser/{sid2}/navigate", json={"url": f"{FIXTURE}/static/catalog.html"})
    r = api_post(f"/eval/{sid2}", json={"code": f"result = await page.evaluate('document.querySelectorAll(\".product\").length')"})
    assert r["result"] == 5

    api_post(f"/browser/{sid2}/screenshot", json={})

    api_delete(f"/sessions/{sid2}")
    print(f"  Headed session scraped catalog, found {r['result']} products via Xvfb")


test("Search results extraction", test_search_extract)
test("Product catalog scrape", test_catalog_scrape)
test("Form fill and submit", test_form_fill_submit)
test("Login authentication flow", test_login_flow)
test("Dynamic content with wait", test_dynamic_content_wait)
test("Multi-page navigation", test_multipage_navigation)
test("Multi-step wizard", test_multistep_wizard)
test("Large page (550 items)", test_large_page)
test("Headed session via Xvfb", test_headed_session_scraping)

api_delete(f"/sessions/{sid}")

print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed+failed}")
if errors:
    print("\nFailures:")
    for name, err in errors:
        print(f"  - {name}: {err}")
print(f"{'='*50}")

sys.exit(1 if failed else 0)
