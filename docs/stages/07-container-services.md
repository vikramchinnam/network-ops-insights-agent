# Stage 7 — The chat app on Snowpark Container Services

**Goal:** a web app with a chat page (and a live trace panel) and an observability page, packaged with Docker and running on Snowpark Container Services, where every question runs as the signed-in user so row access policies apply in the UI too.

**Done when:** the app runs locally, in Docker, and on Container Services; a partner sees only partner data through the app; a 2–3 minute demo video is recorded; the service and pool are suspended; and the work is merged through a PR.

**Time:** 2–3 days.

---

## How it fits together

```
Browser ──Snowflake sign-in──► public endpoint ──► container: FastAPI app  (NOI_DEV.SPCS.NOI_APP)
                                                     │  login token = <service token>.<user token>
                                                     ▼  caller's rights: runs as YOU, with your default role
                                    agent chosen by role: internal or partner
                                    row access policies + grants apply ── partners see only their data
                                                     │
                                    OPS.APP_REQUESTS ◄── every question and its full trace (written as the service)
```

| Piece | File | What it does |
| --- | --- | --- |
| Backend | `spcs/app/main.py` | `/api/chat`, `/api/whoami`, `/api/observability`, `/api/requests/{id}`, `/healthz` |
| Connections | `spcs/app/snowflake_access.py` | Local: key pair as a persona role. SPCS: caller's rights token |
| Trace | `spcs/app/trace.py` | Turns the agent response into steps: planning, tool calls, SQL, results |
| UI | `spcs/app/static/` | Chat + trace panel, observability page. Plain HTML/JS, no build step |
| Image | `spcs/Dockerfile` | Slim Python 3.12, pinned dependencies, non-root user |
| Service | `spcs/service_spec.yaml` | Container, public endpoint, readiness probe, `executeAsCaller: true` |
| Infrastructure | `infra/sql/07_spcs.sql` | `NOI_SPCS` role, X-Small pool (starts suspended), image repository, caller grants |
| Operations | `spcs/deploy_service.py` | `deploy`, `status`, `logs`, `url` |

**Caller grants, in one sentence:** with caller's rights, the app can only use privileges that the signed-in user has **and** that `07_spcs.sql` explicitly allows for the service owner. It's an upper bound, so the app can never do more than the user could.

---

## Part A — Run it locally

### 1. Branch and add the files

```powershell
cd "C:\working\Agentic AI\network-ops-insights-agent"
git checkout main
git pull
git checkout -b stage-7-container-services
```

Copy the Stage 7 files in, then `git status`.

### 2. Install and test

```powershell
uv sync
uv run pytest
```

**Check:** `34 passed`. Eight new tests run the app against a fake Snowflake backend.

### 3. Snowflake setup

```powershell
snow sql -f infra/sql/07_spcs.sql -c noi
uv run python snowpark/deploy_ops.py setup --env dev
uv run python snowpark/deploy_ops.py grants --env dev
```

- `07_spcs.sql`: the `NOI_SPCS` role, the compute pool (suspended, no cost yet), the `SPCS` schema, the image repository and the caller grants. It ends with `SHOW CALLER GRANTS`, which lists what the app may do as a user.
- `setup`: adds the `OPS.APP_REQUESTS` table (the app's request log).
- `grants`: lets `NOI_SPCS` write that log and internal roles read it.

If a line in section 5 of `07_spcs.sql` errors (newer object types), run the remaining lines and tell me which one failed.

Wake the search services if you ran teardown:

```powershell
cd dbt
uv run dbt build --select search_documents public_documents
cd ..
```

### 4. Run the app on your laptop

```powershell
$env:NOI_LOCAL_ROLE = "NOI_SUPPORT"
uv run uvicorn app.main:app --app-dir spcs --port 8080
```

Open http://localhost:8080. The header shows your user, `NOI_SUPPORT` and the `NETWORK_OPS_AGENT` badge.

- Click a suggested question. The answer appears on the left; the **trace** on the right shows each step: planning, the tool calls, the SQL the agent ran, the search query.
- Open **Observability**: eval runs, credits per day by category, credits per request, and your requests. Click a request to reload its trace.

Now be a partner. Stop the server (Ctrl+C), then:

```powershell
$env:NOI_LOCAL_ROLE = "NOI_PARTNER_PTR_001"
uv run uvicorn app.main:app --app-dir spcs --port 8080
```

The badge switches to `NETWORK_OPS_PARTNER_AGENT`. Ask *"List every customer you can see, with its partner."*: only PTR-001's customers. **Observability** says it's available to internal roles only.

---

## Part B — Run it in Docker

### 5. Install Docker Desktop

Download Docker Desktop for Windows from docker.com, install it with the **WSL 2** backend (the default), and start it. Check:

```powershell
docker version
```

Both Client and Server sections should appear.

### 6. Build the image

```powershell
docker build --platform linux/amd64 -t noi_app:v1 spcs
```

`--platform linux/amd64` is what Container Services runs. The first build downloads the Python base image; later builds reuse cached layers.

### 7. Run the container locally

```powershell
docker run --rm -p 8080:8080 `
  -e SNOWFLAKE_ACCOUNT=$env:SNOWFLAKE_ACCOUNT `
  -e SNOWFLAKE_USER=$env:SNOWFLAKE_USER `
  -e SNOWFLAKE_PRIVATE_KEY_PATH=/keys/noi_rsa_key.p8 `
  -e NOI_LOCAL_ROLE=NOI_SUPPORT `
  -v "$HOME\.snowflake\keys:/keys:ro" `
  noi_app:v1
```

Open http://localhost:8080: the same app, now from the image. The key is mounted read-only at run time and is never inside the image.

---

## Part C — Deploy to Snowpark Container Services

### 8. Push the image to Snowflake

```powershell
snow spcs image-registry login -c noi --role NOI_SPCS
$repo = snow spcs image-repository url images --database NOI_DEV --schema SPCS --role NOI_SPCS -c noi
$repo
docker tag noi_app:v1 "$repo/noi_app:v1"
docker push "$repo/noi_app:v1"
```

**Check** in Snowsight (role `NOI_SPCS`):

```sql
SHOW IMAGES IN IMAGE REPOSITORY NOI_DEV.SPCS.IMAGES;
```

### 9. Create the service

Preview, then deploy:

```powershell
uv run python spcs/deploy_service.py deploy --env dev --tag v1 --dry-run
uv run python spcs/deploy_service.py deploy --env dev --tag v1
```

The pool resumes and the container starts; this takes a few minutes. Watch it:

```powershell
uv run python spcs/deploy_service.py status --env dev
```

Repeat until the status is `READY`. If it shows `FAILED` or keeps restarting:

```powershell
uv run python spcs/deploy_service.py logs --env dev
```

### 10. Open the app

```powershell
uv run python spcs/deploy_service.py url --env dev
```

Open the URL and sign in with your Snowflake user. **Caller's rights uses your default role**, so set one that the endpoint is granted to and that sees all data:

```sql
USE ROLE SECURITYADMIN;
ALTER USER <your_login_name> SET DEFAULT_ROLE = NOI_SUPPORT;
```

The header should show `NOI_SUPPORT` and the internal agent. Ask a question and watch the trace.

**See the partner experience through the real endpoint:**

```sql
USE ROLE SECURITYADMIN;
ALTER USER <your_login_name> SET DEFAULT_ROLE = NOI_PARTNER_PTR_001;
ALTER USER <your_login_name> SET DEFAULT_SECONDARY_ROLES = ();
```

Open the URL in a **private/incognito window** (a fresh sign-in). The header shows `NOI_PARTNER_PTR_001` and the partner agent; questions return only PTR-001 data; Observability is denied. Then restore your user:

```sql
USE ROLE SECURITYADMIN;
ALTER USER <your_login_name> SET DEFAULT_ROLE = NOI_SUPPORT;
ALTER USER <your_login_name> SET DEFAULT_SECONDARY_ROLES = ('ALL');
```

### 11. Record the demo (2–3 minutes)

Use Windows' built-in recorder (Win + Alt + R, or the Snipping Tool's video mode). Show:
1. Ask *"Why are hospitals seeing roaming problems, and what should they do?"*; open the trace: SQL, then the KB search.
2. The Observability page: eval history, credits per day, credits per request; click a request to see its trace.
3. The partner view in a private window: only their customers, Observability denied.

Put the video link and two screenshots in the README.

### 12. Stop paying for the pool

```powershell
snow sql -f infra/sql/99_teardown.sql -c noi
```

It now suspends the service and the compute pool (and everything from earlier stages). To bring the app back later: `uv run python spcs/deploy_service.py deploy --env dev --tag v1` (or `ALTER SERVICE NOI_DEV.SPCS.NOI_APP RESUME;`); the pool resumes automatically.

Container costs now appear in `91_cost_report.sql` (last query).

### 13. Commit through a PR

```powershell
git add .
git status        # no keys, no .env
git commit -m "feat(spcs): chat app with trace and observability pages on Snowpark Container Services"
git push -u origin stage-7-container-services
gh pr create --fill
```

Add the demo link and a screenshot to the PR description, merge, then `git checkout main`, `git pull`.

---

## What you should be able to explain

- **The SPCS building blocks:** image repository (where images live), compute pool (the machines), service + spec (what runs, with which ports and capabilities), endpoint (the URL, behind Snowflake sign-in).
- **Caller's rights:** the app combines its own token with the user's token, so every query runs as that user. Row access policies, grants and the partner/internal agent split all carry through to the UI with no extra code.
- **Caller grants:** an administrator-defined upper bound on which of the user's privileges the app may use.
- **Two identities in one app:** questions run as the user; the request log is written as the service. The service never reads business data as itself.
- **One image, two modes:** the same code runs locally with a key pair and a persona role, and in SPCS with caller's rights, detected automatically.
- **Image practices:** slim base, pinned versions, non-root user, `linux/amd64`, secrets mounted at run time, never baked in.
- **Cost model:** the pool bills while running, even idle, so the service and pool are suspended when not in use.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `docker version` shows no Server | Docker Desktop not running | Start Docker Desktop and wait for it to be ready |
| `docker push` unauthorized | Registry login expired | Rerun `snow spcs image-registry login` |
| Service never READY; logs show image errors | Image path or tag mismatch | `SHOW IMAGES IN IMAGE REPOSITORY NOI_DEV.SPCS.IMAGES`; redeploy with the pushed tag |
| Status `PENDING` for several minutes | Compute pool resuming | Normal on first start; wait |
| Browser 403 after sign-in | Your default role can't use the endpoint | Default role must be `NOI_SUPPORT`, a partner role, or an admin role |
| `whoami` shows "Could not connect to Snowflake" in SPCS | Caller grant missing for the database or warehouse | Rerun `07_spcs.sql` sections 4–5; `SHOW CALLER GRANTS TO ROLE NOI_SPCS` |
| Answers fail with privilege errors on the agent, semantic view or search | A section 5 caller grant didn't apply | Tell me which line errored in `07_spcs.sql` |
| Partner sees all data through the endpoint | Default secondary roles still on | `ALTER USER ... SET DEFAULT_SECONDARY_ROLES = ()`, sign in again in a private window |
| Local run: `KeyError: 'SNOWFLAKE_ACCOUNT'` | Env vars not in this terminal | See Stage 2, step 3 |
