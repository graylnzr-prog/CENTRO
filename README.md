# Store Report SaaS MVP

Build the smallest possible product that proves:

**User connects data -> receives useful report -> wants it again**

## MVP scope

Only four features matter for the first version:

1. Data input
   - Upload CSV
   - Or connect a Shopify store with Shopify login
2. Report generation
   - Total sales
   - Sales trend
   - Top products
   - This week vs last week
3. Email delivery
   - Send the report by email
   - Optional chart image later
4. Basic scheduling
   - Daily or weekly
   - Cron/manual is fine for v1

## Starter structure

```text
/app
  main.py
  shopify.py
  reports.py
  emailer.py
  scheduler.py
/database
  db.sqlite
/output
  /reports
```

## Fastest stack

- Backend: FastAPI
- Processing: Pandas
- Storage: SQLite
- Hosting: Render or Fly.io
- Scheduling: cron, GitHub Actions, or a manual trigger

## 7-10 day build plan

### Day 1
- Initialize FastAPI app and folder structure
- Add CSV upload endpoint
- Define a standard sales CSV format

### Day 2
- Parse CSV with Pandas
- Generate initial report values:
  - total sales
  - top products
  - date-based grouping
- Save report output in `/output/reports`

### Day 3
- Add charts for daily and weekly trend
- Create this week vs last week comparison logic
- Decide a single report payload format for API + email

### Day 4
- Add Shopify login flow
- Save the store token after OAuth completes
- Normalize Shopify order data into the same structure as CSV input

### Day 5
- Add polished dashboard UI
- Show upload/connect state, report cards, and a simple chart
- Keep the UI focused on one happy path

### Day 6
- Add email sending with SMTP or a transactional provider
- Send report summary text first
- Attach chart image only if it is easy

### Day 7
- Add schedule creation flow
- Store daily/weekly preferences in SQLite
- Run scheduled jobs with cron or a manual admin button

### Day 8
- Add basic auth or a private admin-only flow
- Improve validation and error handling
- Add loading, empty, and failed states in the UI

### Day 9
- Deploy to Render/Fly
- Test real CSV uploads, real email delivery, and one end-to-end scheduled run
- Fix rough edges and remove dead UI paths

### Day 10
- Polish onboarding
- Tighten report copy so the output feels valuable
- Add one retention hook:
  - "Send this every week"
  - "Email this to my team"

## Success criteria

The MVP is successful if a user can:

1. connect data in under 3 minutes,
2. receive a report that feels useful,
3. ask for the next report without being pushed.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Try the included [sample_sales.csv](C:\Users\Administrator\Documents\New%20project\sample_sales.csv) on the dashboard to see the happy path immediately.

For Shopify, connect through Shopify login. The app will ask for the store domain at login time, then return to the dashboard after approval. Set `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, and `APP_BASE_URL` so the OAuth callback can complete. In your Shopify app settings, add this redirect URL:

```text
{APP_BASE_URL}/auth/shopify/callback
```

By default the app requests `read_orders` and calls Shopify GraphQL Admin API version `2026-04`; override with `SHOPIFY_SCOPES` or `SHOPIFY_API_VERSION` if needed.

If you see this error:

```text
{"detail":"Shopify OAuth is not configured. Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET."}
```

set these environment variables in Render and redeploy:

- `SHOPIFY_CLIENT_ID`
- `SHOPIFY_CLIENT_SECRET`
- `APP_BASE_URL`

## Deploy on Render

This repo now includes [render.yaml](C:\Users\Administrator\Documents\New%20project\render.yaml) for a simple web service deploy.

### Render setup

1. Push this project to GitHub.
2. In Render, create a new Blueprint or Web Service from the repo.
3. Render will use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set the environment variables from [.env.example](C:\Users\Administrator\Documents\New%20project\.env.example).
5. Optionally point Render health checks at `/health`.

### Required environment variables

- `SHOPIFY_API_VERSION`
- `SHOPIFY_CLIENT_ID`
- `SHOPIFY_CLIENT_SECRET`
- `SHOPIFY_SCOPES`
- `APP_BASE_URL`
- `JOB_RUN_TOKEN`
- `RESEND_API_KEY`
- `RESEND_FROM`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Recommended production setup: use `RESEND_API_KEY` and `RESEND_FROM`, which sends mail over HTTPS and fits Render better than raw SMTP. If Resend is not configured, the app falls back to SMTP. If neither is configured, it stays in preview mode and returns the composed report body instead of sending it.

### Resend setup

1. Create an account at [Resend](https://resend.com).
2. Verify a sending domain.
3. Create an API key.
4. Add these to Render:
   - `RESEND_API_KEY`
   - `RESEND_FROM`

Example `RESEND_FROM` value:

```text
SignalStack <reports@yourdomain.com>
```

### Production note

SQLite works for the MVP, but Render's local filesystem is not durable across service restarts unless you attach a persistent disk. For a real recurring-report workflow, either:

- attach a Render disk for `/database` and `/output`, or
- move schedules and generated reports to a hosted database/object storage later.

For portability, the repo also includes [Procfile](C:\Users\Administrator\Documents\New%20project\Procfile) and [\.gitignore](C:\Users\Administrator\Documents\New%20project\.gitignore).

## Scheduled report sending

Schedules now store enough source metadata to rerun CSV and Shopify reports later.

You can trigger due schedules in two ways:

1. HTTP endpoint:
   - `POST /jobs/run-schedules`
2. Local/script runner:
   - `python run_schedules.py`

Recommended Render setup for reliability:

- keep schedules and SQLite inside the web service
- create a Render cron job that calls the web service endpoint instead of reading its own local SQLite file
- protect the endpoint with `JOB_RUN_TOKEN`

Example Render cron command:

```bash
curl -X POST https://your-service.onrender.com/jobs/run-schedules -H "X-Job-Token: $JOB_RUN_TOKEN"
```

This works better than `python run_schedules.py` in a separate Render cron service because the web app and the scheduler read the same SQLite database and output folder.

## Notes

- Keep Shopify integration shallow at first.
- Use one normalized dataset shape for both CSV and Shopify.
- Avoid building a large settings system before users ask for it.
