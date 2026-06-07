# Sales Dashboard

Sales Dashboard turns a CSV upload into a useful sales report, email, and scheduled follow-up.

## What it does

1. Upload a CSV and generate a report.
2. Email the report to a recipient.
3. Save daily or weekly schedules.
4. Sign in with Google through Clerk before using private actions.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create a local `.env` file from [.env.example](C:\Users\Administrator\Documents\New%20project\.env.example).

## Required environment variables

- `APP_SESSION_SECRET`
- `APP_BASE_URL`
- `APP_DATA_DIR`
- `CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_ALLOWED_ORIGINS`
- `RUN_SCHEDULES_TOKEN`
- `RESEND_API_KEY`
- `RESEND_FROM`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

`APP_DATA_DIR` lets the app keep SQLite data and generated reports under a persistent directory on Render. The included Render config mounts a persistent disk and points it at `/opt/render/project/src/data`.

`RUN_SCHEDULES_TOKEN` must be the same value on the web service and cron service. The cron uses it to call `/jobs/run-schedules` without a browser session.

## Deploy on Render

1. Push this repo to GitHub.
2. Create a Render web service from the repo.
3. Set the environment variables above.
4. Keep the health check path at `/health`.
5. Deploy.

## Scheduled reports

The included Render Blueprint creates a cron service that runs every 15 minutes and triggers due schedules through the web app:

```bash
python trigger_due_schedules.py
```

You can also trigger due schedules through the dashboard's "Run due schedules now" button while signed in. For local development, you can run due schedules directly against the local SQLite database:

```bash
python run_schedules.py
```

## Notes

- The app uses SQLite for now.
- Disable password-based sign-in methods in the Clerk Dashboard so Google is the only provider at the account level.
- Resend is the preferred email path for production; SMTP stays as a fallback.
