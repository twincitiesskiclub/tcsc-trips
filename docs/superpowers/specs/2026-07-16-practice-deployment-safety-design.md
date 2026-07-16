# Practice Announcement Deployment Safety Design

Date: 2026-07-16
Status: Design direction approved; written specification pending final review

## Goal

Close the three release-safety gaps found in final review without changing the
approved announcement design:

1. Restore a practice announcement if Slack cleanup succeeds but the database
   delete does not.
2. Make Coach and public weekly-summary posts belong to a calendar week rather
   than to an individual practice.
3. Never report that the reaction-default seed "aborted" after its transaction
   already committed.

The implementation stays deliberately small: one summary-identity table, one
delete-recovery path, and one distinct post-commit seed error.

## 1. Canonical weekly-summary identity

Add `PracticeSummaryPost`, keyed by `(week_start, surface)`, with:

- `week_start`: Monday calendar date;
- `surface`: `coach_summary` or `weekly_summary`;
- `channel_id`: Slack channel containing the post;
- `message_ts`: Slack timestamp for the post;
- normal created/updated timestamps.

The pair `(week_start, surface)` is unique. This table is authoritative for a
weekly post's identity. The existing timestamp columns on `Practice` remain as
temporary compatibility mirrors; this release does not remove them.

Production posting routines upsert the registry row after Slack returns a
timestamp, including when the week has zero practices. Dry runs and
channel-override previews never register themselves.

If that registry commit fails after a new Slack post is created, use the
project's existing one-attempt compensation pattern: delete the new post, or
persist its known identity once if deletion fails. Never leave an unreported
orphan.

The migration backfills one registry row for every existing linked week and
surface. It fails instead of choosing arbitrarily if a week has conflicting
legacy timestamps. A read-only production check on 2026-07-16 found zero such
conflicts.

## 2. Summary refresh behavior

Summary refreshes resolve the Slack post from `(week_start, surface)`, then
query the current practices in that week and update that exact post.

- Create refreshes the new practice's week if a registered summary exists.
  It does not create a new summary outside the scheduled posting workflow.
- Same-week edit, cancellation, and workout changes refresh that one week.
- A cross-week date edit refreshes the distinct source and destination weeks.
  The source loses the moved practice; the destination gains it when that
  week's summary exists. One week's timestamp is never reused for another.
- Delete refreshes the affected week while explicitly excluding the row that
  has not yet been committed as deleted.
- Coach-summary edit logs resolve the current week's registered Coach post.

Admin Create/Edit and Slack Create/Quick Edit/Full Edit use the same helpers.
This also covers a practice created after an initially empty weekly post.

## 3. Failed-delete compensation

Keep the existing Slack-first delete order. It prevents a database row from
being removed when Slack cannot safely preserve or remove the announcement.

Before cleanup, capture the original announcement channel/root and practice
week. If Slack cleanup is partial or the final database commit fails:

1. roll back and reload the practice;
2. if the row no longer exists, report that deletion committed and do not
   recreate it;
3. if its original root still exists, rebuild it from the surviving row;
4. if a standalone root was deleted, repost it once in its original channel;
5. rebuild the affected registered summaries without excluding the practice.

Recovery is attempted once. There is no retry loop or outbox. The response and
logs distinguish a restored practice from an ambiguous/incomplete recovery;
they never claim that an undeleted row is safely synchronized when it is not.

## 4. Seed commit reporting

Keep the existing digest approval, locked recheck, atomic fill transaction, and
independent read-back.

Introduce a distinct post-commit verification failure. The CLI handles it
before ordinary pre-commit `SeedPlanError` failures and prints an unmistakable
message equivalent to:

`COMMIT SUCCEEDED; VERIFICATION FAILED OR UNKNOWN`

It exits nonzero and instructs the operator to run a new dry run/read-back. It
must not print `Seed aborted`, because the approved writes may already be
durable. Pre-commit validation, digest drift, conflicts, and write failures
continue to report an abort with no successful commit.

## 5. Migration and deployment

The Render migration runs while the old service may still be live. During the
short migration/cutover window, practice creation and editing must remain
quiet so the old writer cannot create an empty reaction snapshot or stale
summary linkage between backfill and process replacement. This is an explicit
deployment operation, not a new maintenance-mode feature.

The local companion remains stopped. Render is the sole production Socket Mode
consumer. A separate TCSC Slack test app remains a documented follow-up.

After deployment:

1. verify the migration head and the new columns/table read-only;
2. test Practice Preview through Render in `C07G9RTMRT3`;
3. run the production seed dry run;
4. show the exact diff and digest for fresh approval;
5. only then run the approved commit and a second read-back dry run.

## 6. Tests and acceptance criteria

Test-first regressions cover:

- failed final database delete restores a standalone announcement;
- failed shared-session delete restores the removed session in the shared root;
- partial Slack cleanup is compensated while the database row remains;
- weekly/Coach posting registers empty and non-empty production weeks, but not
  previews;
- Admin and Slack late-create paths refresh an existing public weekly summary;
- cross-week Admin, Slack Quick Edit, and Slack Full Edit refresh the old and
  new week using their own identities;
- moving the only practice leaves the old empty summary registered;
- migration backfill rejects conflicting legacy timestamps;
- post-commit seed verification failure is reported as committed-but-unverified;
- pre-commit seed failures still report an abort.

Acceptance requires focused suites, the full Python and Node suites, a clean
Tailwind rebuild, `git diff --check`, and final code re-review before merge.
