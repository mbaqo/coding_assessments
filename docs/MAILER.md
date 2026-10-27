# Daily interview email automation

The public repository contains the code and curriculum. A dedicated Gmail account sends each active recipient their next five questions daily. Each person has their own position in a shared question sequence: pausing preserves that position, and new subscribers start at batch 1. There are no learner accounts and no completion tracking. Not answering never pauses delivery.

For example, if both people receive batch 1 and one pauses for two days, the other receives batches 2 and 3. When the paused person replies `RESUME`, they receive batch 2 while the other receives batch 4. There is no catch-up burst. Commands are parsed by Python; AI generates the questions, not subscription decisions.

Python runs in GitHub Actions. A free external timer dispatches the workflow, avoiding GitHub's 60-day inactivity cutoff for scheduled workflows in public repositories. A private Google Sheet stores mailing state. Do not make that Sheet public.

## Automatic question supply

Once the API credentials and daily timer below are configured, no developer session or manual request for questions is needed. Every scheduled ` -pythonm mailer run`:

1. Processes replies and determines each active person's next batch.
2. Reuses that batch from the private Sheet if it already exists.
3. If someone needs a batch beyond the saved sequence, calls Gemini to draft exactly five questions, validates them, requests an AI review, and saves the approved batch before sending it.
4. Sends each person their next batch and records the confirmed delivery.

Generated email questions live in the Sheet; you do not need to create new `days/day_NN/` repository folders. The runtime reads `CURRICULUM.md` itself to guide generation. People at the same position reuse the same questions, keeping generation to at most one new batch per calendar day for the group.

If Gemini is unavailable or a batch fails validation/review, the mailer sends five saved review questions (using the bundled five if no generated questions exist). These may repeat and do not advance the person's position. It automatically tries generation again on the next day it needs a new batch. This keeps question supply available during an AI outage, but cannot guarantee fresh questions every day or delivery during an email/storage outage.

The workflow only has a `workflow_dispatch` trigger: the external timer in step 6 must be enabled for unattended runs. The code in this repository alone does not activate that timer or configure API credentials.

## Try it offline

Python 3.9+ is sufficient for the runtime, preview, and tests. Actions uses Python 3.12. On Windows, install `tzdata` if your Python installation lacks IANA timezone data.

```bash
python3 -m mailer preview
python3 -m unittest discover -s mailer/tests -v
python3 practice.py check
```

Preview reads the five existing exercise prompts without executing learner code. It makes no network calls, sends nothing, and changes no files.

`mailer/config.example.json` is the actual nonsecret configuration used by the workflow. Change it to adjust the timezone, send time, days per syllabus stage, subscriber cap, or Gemini model. Local commands use these same defaults; after changing the file, pass `--config mailer/config.example.json` **before** the subcommand.

## 1. Prepare the dedicated Gmail account

Use a separate Gmail account for the mailer, with a primary username of at most 30 characters and no `+` suffix. Recipients can use other email providers. They do not authorize an app or create accounts.

1. Create a Google Cloud project and enable **Gmail API** and **Google Sheets API**. These integrations do not require enabling paid Gemini usage.
2. Configure the OAuth consent screen for your application. Authorize only the dedicated sending account. If the app is in Testing, add that account as a test user.
3. Before unattended operation, change the publishing status to **In production**. Gmail-scoped refresh tokens issued while an external app is in Testing normally expire after seven days. Reauthorize after switching status. Personal-use authorization may display an unverified-app notice; production status does not itself mean Google has verified the app.
4. Create an OAuth client of type **Desktop app**, download its JSON, and save it as `.mailer-private/client.json`. This directory is ignored by Git.
5. Authorize locally:

If Google requires a homepage and privacy-policy URL before switching to production, publish the included `site/` pages using the [GitHub Pages guide](WEBSITE.md), then enter the live URLs on the Branding page.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r mailer/requirements-setup.txt
python -m mailer oauth-setup --client .mailer-private/client.json
```

Sign in as the dedicated sending account. The helper requests Gmail read-only, Gmail send, and Sheets access, uses a local browser callback with PKCE, and saves `.mailer-private/google-credentials.json` with owner-only permissions. It refuses to overwrite an existing credentials file.

Load credentials into your local shell without displaying them:

```bash
export MAILER_GOOGLE_CREDENTIALS="$(cat .mailer-private/google-credentials.json)"
export MAILER_SENDER='your.dedicated.account@gmail.com'
```

OAuth tokens can still be revoked or invalidated later. An authorization failure stops that run without altering subscriptions; reauthorize locally and replace the GitHub secret when necessary.

References: [Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [refresh-token expiration](https://developers.google.com/identity/protocols/oauth2/#expiration), [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes).

## 2. Initialize private mailing state

```bash
python -m mailer init-state
```

This creates a new private spreadsheet and prints its ID. Save the ID locally:

```bash
export MAILER_SHEET_ID='your-spreadsheet-id'
```

The `MailerState` tab stores one JSON record per row, including subscriptions, received command IDs, saved batches, and delivery status. It uses raw values, so text cannot become a spreadsheet formula. Do not edit the generated rows during operation. Malformed or missing state fails closed and is never automatically reset.

Mailing position is calculated from each person's confirmed daily deliveries. Each new daily delivery records the saved batch's creation date separately from its send date. Review and setup-test emails do not advance that position. Existing state needs no manual migration: older records use their send date to identify the batch, and existing subscribers continue after their last confirmed fresh batch. This does not retroactively recover batches skipped before this change. No answers, solved-question flags, or mastery scores are stored by the mailer.

Only one writer is supported. GitHub Actions serializes mailer runs. Before local administrative changes, pause the external timer, wait for any running workflow to finish, make the change, then restore the timer. Do not run the CLI simultaneously from another machine. Keep a private backup of the Sheet before manual repairs.

## 3. Configure free-tier Gemini

Use your existing Google login to create an API key in [Google AI Studio](https://aistudio.google.com/). Select a **free-tier API project with no linked billing account**. Gemini app subscriptions and API project quotas are separate; inspect the project's active limits rather than assuming your subscription increases them.

Set the API key locally without putting it in shell history:

```bash
read -r -s -p 'Gemini API key: ' GEMINI_API_KEY
export GEMINI_API_KEY
export MAILER_GEMINI_FREE_TIER_CONFIRMED=true
python -m mailer check-model
```

The default model is `gemini-3.1-flash-lite`. `check-model` verifies that your key can retrieve metadata for that model and that it supports generation. It does **not** prove billing status, available quota, or question quality. Check those in AI Studio. If this model is unavailable, select a currently available free-tier text model in the configuration and check again.

The confirmation flag is an operator acknowledgment, not an API-enforced spending cap. Never point this deployment at a billing-enabled project if spending must remain zero. The program cannot infer billing status from a Gemini API key and never enables billing itself.

Generation uses at most one draft call and one review call per calendar day for the whole group. There are no automatic model retries, web-search tools, or per-recipient generation calls. Missing credentials, unconfirmed free-tier status, exhausted quotas, rejected reviews, and invalid responses produce a saved review batch instead. Free-tier prompts may be used by Google to improve its products; recipient addresses, subscription records, and incoming mail are never sent to Gemini.

References: [Gemini billing](https://ai.google.dev/gemini-api/docs/billing), [project-level limits](https://ai.google.dev/gemini-api/docs/rate-limits), [pricing and data use](https://ai.google.dev/gemini-api/docs/pricing).

## 4. Test with yourself, then enroll the group

Enroll your personal recipient address, which must differ from the dedicated sending account:

```bash
python -m mailer subscribers add --email 'your.personal.address@example.com'
python -m mailer subscribers list
python -m mailer send-test --email 'your.personal.address@example.com'
```

`add` only changes the list; it sends nothing. `send-test` sends the fallback questions without a Gemini call. Tests are deduplicated per recipient/day. Reply `PAUSE`, then run the mailer to confirm command handling. Reply `RESUME` to that email and run again when you want delivery to resume.

```bash
python -m mailer run
```

`run` is live: it processes replies and, if the configured time has passed, sends each active recipient their next batch. Before the configured time it only processes commands and confirmations. It sends at most one daily email per person per local calendar day, without backfilling missed calendar days. `subscribers list` shows each person's status and next batch number.

Add each invited recipient with the same `subscribers add` command. The default cap is 25 non-stopped subscribers. Do not enroll addresses without consent. No public signup endpoint exists in this version.

## 5. Configure GitHub Actions

The repository can remain **public**. The mailer workflow has no `schedule` trigger and only runs through `workflow_dispatch`. Sending is disabled until you set the repository variable `MAILER_ENABLED=true`.

In **Settings → Secrets and variables → Actions**, add these repository secrets:

| Secret | Value |
| --- | --- |
| `MAILER_GOOGLE_CREDENTIALS` | Entire `.mailer-private/google-credentials.json` file |
| `MAILER_SENDER` | Dedicated Gmail address |
| `MAILER_SHEET_ID` | Private state spreadsheet ID |
| `GEMINI_API_KEY` | Key for your free-tier Gemini API project |

Add these repository variables:

| Variable | Value |
| --- | --- |
| `MAILER_ENABLED` | `true` after the controlled test succeeds |
| `MAILER_GEMINI_FREE_TIER_CONFIRMED` | `true` only after checking the project has no billing account |

With an authenticated GitHub CLI, secrets can be set without printing them:

```bash
gh secret set MAILER_GOOGLE_CREDENTIALS < .mailer-private/google-credentials.json
gh secret set MAILER_SENDER
gh secret set MAILER_SHEET_ID
gh secret set GEMINI_API_KEY
gh variable set MAILER_GEMINI_FREE_TIER_CONFIRMED --body true
gh variable set MAILER_ENABLED --body true
```

Enable Actions and manually dispatch **Daily interview mailer** on `main` once. The workflow refuses non-default branches. PR checks use no credentials. The runtime logs aggregate counts only; administration commands refuse to run inside public Actions logs.

Anyone with repository write access can modify code that uses repository secrets. Restrict write access and review changes before merging. Do not upload credentials, state files, or raw email artifacts to Actions.

## 6. Set the external timer

Create a free account at [cron-job.org](https://cron-job.org/en/). Create a fine-grained GitHub token restricted to this repository with **Actions: read and write** permission. Choose an expiry you can maintain and track its renewal.

Create a job with:

| Setting | Value |
| --- | --- |
| URL | `https://api.github.com/repos/mbaqo/coding_assessments/actions/workflows/mailer.yml/dispatches` |
| Method | `POST` |
| Timezone | `America/Los_Angeles` |
| Schedule | Every day at 08:15 and 08:45 (custom minute values 15,45; hour 8) |
| Header | `Authorization: Bearer YOUR_REPOSITORY_SCOPED_TOKEN` |
| Header | `Accept: application/vnd.github+json` |
| Header | `Content-Type: application/json` |
| Header | `X-GitHub-Api-Version: 2026-03-10` |
| Body | `{"ref":"main"}` |

For a fork, replace the owner/repository and default branch. If you change the mailer's timezone/send time, update this external schedule too. The second dispatch retries definite send failures and reconciles interrupted runs; it does not resend completed deliveries or regenerate the batch.

Enable failure notifications in cron-job.org and GitHub Actions. A successful dispatch response means GitHub accepted the request, **not** that the email job succeeded; inspect Actions run results as well. Renew the external token before it expires. Keep the token only in the scheduler's protected configuration, never the public repository.

This avoids the inactivity rule applying to GitHub's native scheduled events. It does not guarantee uninterrupted delivery during Gmail, Google Sheets, scheduler, GitHub, or credential outages. References: [GitHub dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event), [schedule inactivity policy](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Reply commands

Put the command on the **first nonempty line** of a reply. Replies must come from the enrolled address and retain the tokenized reply destination. Replies from aliases or manually sent to the base Gmail address are ignored.

| Command | Result |
| --- | --- |
| `PAUSE` | Indefinite pause, keeping your place |
| `PAUSE N` | Pause for 1–365 days, measured as 24-hour intervals from receipt |
| `RESUME` | Resume a paused subscription at your next batch |
| `STOP` or `UNSUBSCRIBE` | Stop indefinitely; no automatic restart |
| `HELP` | Send instructions and current status |

Case does not matter. Signatures and quoted text do not supply commands. Unknown replies and code answers are ignored. Commands are normally processed at the next 08:15 or 08:45 run, followed by a confirmation. A message already being sent cannot be recalled. Checking continues while everyone is paused or stopped.

After a stop, the organizer can explicitly reenroll a consenting recipient:

```bash
python -m mailer subscribers reenroll --email 'recipient@example.com'
```

Reenrollment preserves the recipient's mailing position. `RESUME` alone does not undo `STOP`; use `PAUSE` for a break you want to end yourself.

Reenrollment rotates the reply token, invalidating commands sent to old reply addresses. Stopping does not erase mailing history. Completion history is never collected.

## Recovery and delivery guarantees

Every batch is saved before sending, and every delivery intent is saved before Gmail is called. A definite HTTP rejection can retry on the next run. A timeout, server error, or crash after intent is recorded can be ambiguous. The next run searches Gmail Sent mail for the deterministic `Message-ID`; if found, it marks the delivery sent without sending again.

If the message cannot be found, the record stays `uncertain` and the job reports a failure. Gmail does not provide an exactly-once send API, and search indexing can lag. Do not assume a missing immediate search result proves delivery failed. Wait, inspect Sent mail and the recipient inbox, then resolve the record locally if necessary:

```bash
python -m mailer resolve-delivery --key 'KEY_FROM_PRIVATE_SHEET' --resolution sent
python -m mailer resolve-delivery --key 'KEY_FROM_PRIVATE_SHEET' --resolution retry
python -m mailer resolve-delivery --key 'KEY_FROM_PRIVATE_SHEET' --resolution cancel
```

Choose **one** resolution. `retry` allows another attempt at the next eligible run; on a later date, the recipient still receives their next unsent batch. A successful reconciliation takes precedence over your requested resolution. Incorrectly choosing retry can create a duplicate, so do it only after checking. An uncertain daily delivery holds that recipient's sequence until resolved; other recipients continue. Marking a delivery `sent` advances their position, while `retry` and `cancel` do not. Cancelling suppresses another attempt on the original date.

An unreadable inbox, invalid Sheet, or failed state write stops the run rather than ignoring a possible unsubscribe request. Authentication and network failures do not change subscription status. Disable `MAILER_ENABLED` for an operator-wide emergency stop; individual users should use reply commands.

## Architecture and extension points

| Module | Responsibility |
| --- | --- |
| `mailer/domain.py` | Configuration, syllabus, reply parsing, rendering |
| `mailer/generation.py` | Structured generation, review, saved fallback |
| `mailer/providers.py` | Gemini and Gmail REST access, OAuth refresh |
| `mailer/storage.py` | Validated private Sheets persistence |
| `mailer/engine.py` | Poll → commands → reconcile → generate → deliver |
| `mailer/__main__.py` | Local setup, administration, preview, and run commands |

The shared question sequence contains 14 fresh batches at each stage. Foundations use five easy questions; core patterns use three easy and two medium; later stages use two easy review questions and three mediums. After advanced patterns, mixed practice continues. A new batch is generated only when an active recipient reaches the end of the saved sequence; people further behind reuse the saved batches. Each person's stage therefore follows their own mailing position. Review emails and days without delivery do not advance that person's position. This measures curriculum exposure, not learning or mastery.

The generation review is an additional model check, not execution-based proof of correctness. No generated code is executed. Deterministic validation and model review reduce malformed content; they cannot eliminate ambiguous or incorrect problems.

Separate provider, storage, generation, and command interfaces allow later additions such as feedback, a database, a different model provider, instant webhooks, or preference pages. The original local practice workflow remains independent and keeps its existing performance-based curriculum rules.
