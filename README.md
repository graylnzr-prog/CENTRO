# Sales Dashboard

Sales Dashboard turns a CSV upload into a useful sales report, email, and scheduled follow-up.

## What it does

1. Upload a CSV and generate a report.
2. Email the report to a recipient.
3. Save daily or weekly schedules.
4. Sign in with an admin username and password before using private actions.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create a local `.env` file from [.env.example](C:\Users\Administrator\Documents\New%20project\.env.example).

## Required environment variables

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `APP_SESSION_SECRET`
- `APP_BASE_URL`
- `APP_DATA_DIR`
- `RESEND_API_KEY`
- `RESEND_FROM`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

`APP_DATA_DIR` lets the app keep SQLite data and generated reports under a persistent directory on Render. The included Render config points it at `/opt/render/project/src/data`.

## Deploy on Render

1. Push this repo to GitHub.
2. Create a Render web service from the repo.
3. Set the environment variables above.
4. Keep the health check path at `/health`.
5. Deploy.

## Scheduled reports

You can trigger due schedules either through the `/jobs/run-schedules` endpoint while signed in or by running:

```bash
python run_schedules.py
```

## Notes

- The app uses SQLite for now.
- Keep the admin username and password out of GitHub.
- Resend is the preferred email path for production; SMTP stays as a fallback.
