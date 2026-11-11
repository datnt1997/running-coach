# This week dashboard

The home page shows the current week of the most recent goal's plan.

## Sub-features

- `dash-empty` with no goals: `Chưa có kế hoạch tập luyện nào.` and a create link.
- `dash-week` with a plan: `Tuần Này`, `Tuần N/12`, that week's workouts, link `Xem toàn bộ kế hoạch →`.
- `dash-upcoming` when the plan starts in the future: `Kế hoạch của bạn sẽ bắt đầu sau {days} ngày nữa`.

## How to get to it (user POV)

- Nav link `Tuần Này` (`/app`).

## Driving it with Claude in Chrome + psql

Preconditions: empty DB for `dash-empty`; a goal for the rest.

- **Empty.** Open `/app`; the empty message shows.
- **With plan.** After `new-goal.md`, open `/app`; heading `Tuần Này` and the week label appear.
- **Upcoming.** A plan created today starts today, so this state needs `psql "$VERIFY_DATABASE_URL" -c "update training_plans set start_date = current_date + 5"`, then reload and expect the upcoming text with 5 days.

## Gotchas

- Not yet run in this skill's proof.
