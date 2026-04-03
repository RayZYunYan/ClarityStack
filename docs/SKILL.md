# ClarityStack OpenClaw Skill

## Purpose

Run the ClarityStack AI content pipeline on a daily heartbeat with a mandatory human approval gate before anything is published.

## Trigger

- Invoke `python automation/pipeline.py --auto` once per day at 9:00 AM local time.
- If a run fails, retry once after 30 minutes.

## Execution rules

1. Start the pipeline with `python automation/pipeline.py --auto`.
2. Preserve all logs written to the `logs/` directory.
3. Do not bypass the approval prompt before publishing.
4. If the run succeeds, notify the configured messaging bridge with the publish URLs.
5. If the run fails, include the error summary and the log path in the notification.

## Operator expectations

- The operator reviews the generated LinkedIn, blog, and X previews.
- Publication only continues after explicit approval.
- If approval is denied, exit cleanly without publishing.
