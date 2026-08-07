---
name: run-app
description: Launch and drive the FBR reconciliation Streamlit app. Use when asked to run, start, restart, or smoke-test the app, or to confirm a change works in the real app rather than only in a script.
---

# Running the FBR reconciliation app

## Launch

```bash
cd /mnt/g/FBR_VS_LOCAL_INV/fbr_reconciliation_app
nohup ./venv/bin/streamlit run app.py --server.headless true --server.port 8501 \
  > /tmp/streamlit_run.log 2>&1 &
disown
```

Use the venv interpreter directly (`./venv/bin/streamlit`) — a bare `streamlit`
is not on `PATH`.

## Wait for it properly

Streamlit takes **~20 seconds** to bind the port on WSL. The log prints its
"You can now view your Streamlit app" banner before the socket is actually
accepting connections, so polling the log is misleading and an early `curl`
returns exit 7. Wait on the port:

```bash
until curl -sf -o /dev/null http://localhost:8501; do sleep 2; done
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501
```

## Restarting

**Do not use `pkill -f streamlit`** — the pattern also matches the agent's own
shell wrapper and kills the session. Kill the listener by PID:

```bash
PID=$(ss -ltnp 2>/dev/null | grep 8501 | grep -oP 'pid=\K[0-9]+' | head -1)
[ -n "$PID" ] && kill "$PID"
```

Streamlit does hot-reload on file change, but session state holds previous
`ReconciliationResult` objects — restart after changing dataclasses or the
pipeline, otherwise stale objects resurface.

## Driving it

The app needs two uploaded Excel files, which can't be supplied over HTTP. There
is no browser automation installed, so an end-to-end UI click-through is not
available. Verify behaviour these two ways instead:

**1. Exercise the pipeline headlessly** against the real files the user last
uploaded, which persist in `/tmp/fbr_reconciliation_work/` (`fbr_updated_*.xlsx`
and `local_updated_*.xlsx` — take the newest pair):

```bash
./venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from processors.reconciliation import reconcile
from services.totals import calculate_tax_total
fp,lp = Path('...fbr_updated_X.xlsx'), Path('...local_updated_Y.xlsx')
diff = calculate_tax_total(fp,'FBR').total - calculate_tax_total(lp,'Local').total
r = reconcile(fp, lp, tolerance=2.0)
print(r.detail['Status'].value_counts())
print('explained OK:', abs(diff - r.summary['Difference Explained']) < 0.01)
"
```

**2. Render UI components with a fake `st`** — they are pure HTML producers, so
a stub with `markdown`, `columns`, `caption`, `write` is enough to confirm they
emit real markup rather than erroring:

```python
class Col:
    def __enter__(self): return self
    def __exit__(self, *a): return False
class FakeSt:
    def markdown(self, s, **k): OUT.append(s)
    def columns(self, n, **k): return [Col() for _ in range(n)]
```

Then assert on probe strings (`hero-title`, `match-seg`, `exp-badge`, `finding`).

## Health check

`HTTP 200` plus no `error`/`traceback` in the log means the app imported and
served cleanly:

```bash
grep -ciE "error|traceback" /tmp/streamlit_run.log
```
