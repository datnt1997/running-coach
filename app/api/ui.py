from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Running Coach</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 480px; margin: 80px auto; padding: 0 1rem; }
    h1 { font-size: 1.5rem; }
    #status { margin: 1.2rem 0; font-size: 1rem; }
    .ok { color: #2a9d2a; }
    .off { color: #888; }
    button { padding: .45rem 1.1rem; font-size: .95rem; cursor: pointer; }
  </style>
</head>
<body>
  <h1>Running Coach</h1>
  <div id="status">Loading…</div>
  <div id="actions"></div>

  <script>
    async function refresh() {
      const r = await fetch('/strava/status');
      const d = await r.json();
      const s = document.getElementById('status');
      const a = document.getElementById('actions');
      if (d.connected) {
        s.innerHTML = '<span class="ok">Connected as athlete ' + d.athlete_id + '</span>';
        a.innerHTML = '<button onclick="disconnect()">Disconnect</button>';
      } else {
        s.innerHTML = '<span class="off">Not connected to Strava</span>';
        a.innerHTML = '<a href="/strava/connect"><button>Connect with Strava</button></a>';
      }
    }

    async function disconnect() {
      await fetch('/strava/disconnect', { method: 'POST' });
      refresh();
    }

    refresh();
  </script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def connect_ui() -> HTMLResponse:
    return HTMLResponse(content=_PAGE)
