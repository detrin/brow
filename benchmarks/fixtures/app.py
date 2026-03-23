import random
from pathlib import Path

from fastapi import FastAPI, Form, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

STATIC_DIR = Path(__file__).parent / "static"

def create_fixture_app():
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    sessions = {}

    @app.post("/form", response_class=HTMLResponse)
    async def form_submit(name: str = Form(...), email: str = Form(...),
                          subject: str = Form("other"), message: str = Form("")):
        return f"""<html><body>
        <h1>Confirmation</h1>
        <p>Thank you, {name}! Your message about '{subject}' has been received.</p>
        <p>We'll reply to {email} shortly.</p>
        </body></html>"""

    @app.post("/login", response_class=HTMLResponse)
    async def login(response: Response, username: str = Form(...), password: str = Form(...)):
        if username == "admin" and password == "password123":
            token = f"session-{random.randint(1000,9999)}"
            sessions[token] = username
            response.set_cookie("auth_token", token)
            return f"""<html><body>
            <h1>Login Successful</h1>
            <p>Welcome, {username}. <a href="/dashboard">Go to Dashboard</a></p>
            </body></html>"""
        return HTMLResponse("<html><body><h1>Login Failed</h1><p>Invalid credentials</p></body></html>", status_code=401)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(auth_token: str = Cookie(None)):
        if auth_token not in sessions:
            return HTMLResponse("<html><body><h1>Unauthorized</h1></body></html>", status_code=401)
        user = sessions[auth_token]
        return f"""<html><body>
        <h1>Dashboard</h1>
        <p>Welcome back, {user}</p>
        <div id="user-data"><span class="username">{user}</span><span class="role">Administrator</span></div>
        <button id="logout">Logout</button>
        </body></html>"""

    @app.get("/dynamic", response_class=HTMLResponse)
    async def dynamic():
        return """<html><head><title>Dynamic Page</title></head>
        <body>
        <h1>Dynamic Content</h1>
        <div id="loading">Loading...</div>
        <div id="dynamic-content" style="display:none">
          <div class="item"><span class="name">Alpha</span><span class="value">100</span></div>
          <div class="item"><span class="name">Beta</span><span class="value">200</span></div>
          <div class="item"><span class="name">Gamma</span><span class="value">300</span></div>
        </div>
        <script>
        setTimeout(() => {
          document.getElementById('loading').style.display='none';
          document.getElementById('dynamic-content').style.display='block';
        }, 2000);
        </script>
        </body></html>"""

    @app.get("/flaky", response_class=HTMLResponse)
    async def flaky():
        show = random.random() > 0.5
        element = '<div id="flaky-element" class="target">Found me!</div>' if show else '<div id="placeholder">Loading...</div>'
        return f"""<html><body>
        <h1>Flaky Page</h1>
        {element}
        <p class="status">{'Element visible' if show else 'Element missing'}</p>
        </body></html>"""

    @app.get("/large", response_class=HTMLResponse)
    async def large():
        items = "\n".join(
            f'<div class="item" data-id="{i}"><span class="label">Item {i}</span>'
            f'<span class="value">{i * 7 % 100}</span>'
            f'<button class="action">Select</button></div>'
            for i in range(550)
        )
        return f"""<html><body>
        <h1>Large Page Test</h1>
        <div id="content">{items}</div>
        </body></html>"""

    return app
