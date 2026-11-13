# Research: weekly availability and missed workouts

Status: done. Supports the domain terms in `GLOSSARY.md` (Weekly availability, Quality workout, Missed workout, Long run, Weekly volume). Page numbers are the printed numbers at the foot of each page in `references/daniels.txt` (Vietnamese edition). They were read from the text file, not the PDF; check a page against the PDF before citing it outside this repo. The book is copyrighted, so this file paraphrases and quotes only short phrases.

## Reading `references/daniels.txt`

The file is the Vietnamese edition, about 1 MB and 17,000 lines. Never read it whole; search, then read a short range.

- **Search in Vietnamese.** Useful terms: `nghỉ tập` (time off), `phiên Q` / `phiên tập Q` (Q session), `chạy E` / `ngày E` (easy run or day), `chạy L` (long run), `quãng đường chạy trong tuần` (weekly distance), `bỏ lỡ` (missed), `ốm`, `chấn thương` (ill, injured), `giai đoạn` (phase), `chương trình 2Q`, `Bảng` (table). Use `grep -n -i -E "a|b" references/daniels.txt | cut -c1-160`, then `sed -n 'START,ENDp'`.
- **Page numbers print at the foot of the page.** A passage belongs to the next page number printed below it, and text after a number is on the following page. To find the page for a line: `awk -v s=LINE 'NR>=s && /^[[:space:]]+[0-9]{1,3}[[:space:]]*$/ {print NR": "$0; exit}' references/daniels.txt`. Reading the number above a passage is the usual mistake (it put Table 15.1 on p. 381; it is on p. 382).
- Check any page you will cite against the PDF.

## R1. What Daniels says about a missed day

- **A missed easy day is not lost training** (p. 84). A day without running can be part of the week ("coi việc tạm nghỉ không chạy bộ cũng là một phần của luyện tập").
- **Do not replace an E day with an extra Q session** (p. 84). E days exist to recover from Q sessions, so adding a Q in their place "không phải là ý hay".
- **Make up distance on the other E days** (p. 84, p. 320). Example on p. 84: spread the remaining distance over the other E days (5 or 8 km each), or put 8 to 10 km on two of them. p. 320 (2Q programme): when a rest day is needed, use the remaining E days of that week to reach the weekly distance target.
- **An E day can hold more than one run** (p. 320): "một, hai, hoặc nhiều hơn nữa các đợt chạy E trong một ngày nếu cần". This is the book's basis for two workouts in a day.
- **Keep 2 or 3 E days between Q days** (p. 320).
- **Do not train hard to catch up after a break** (p. 376): "đừng cố tập quá lên để bù đắp cho quãng thời gian bị mất". Resume below the earlier volume.
- **Do not train when ill or injured** (principle 8, p. 30). Skipping a few days costs less than training through.
- **VDOT after time off** (Table 15.1, p. 382): up to 5 days off leaves VDOT at factor 1.000. One missed workout never lowers VDOT. `app/vdot.py:break_factor` already encodes this table.

## R2. Limits on distance

- **Long run L** (p. 85): at most 30% of the week's distance when the week is under 64 km; under 25% when the week is 64 km or more, or 150 minutes, whichever comes first.
- **Hold weekly distance steady for 4 weeks before raising it** (p. 85).
- **Raising it** (p. 302, half-marathon chapter): add 1.6 km per run per week, never more than 16 km in total.
- **The book gives no percentage cap on one workout's growth, and no cap on a week's overshoot.** An earlier draft used 20% per workout and 10% per week; both were invented and are not used.
- Worked case: a 66 km week has a Long run limit of 25%, about 16.5 km.

## R3. What counts as a Quality (Q) session

- Q sessions are T, I, R and M work. In some phases the long run L counts as a Q session (p. 226, plans of 32 to 48 km a week: "bài chạy L được tính là một phiên Q"). The glossary therefore counts a long run as Quality only when it includes faster running.
- Phases in the 5K/10K programmes (about pp. 262-266): II is repetition work, III is interval work, IV is final quality work (T with some R). Phase I is foundation. `GLOSSARY.md` uses these as Phase I to IV.

## R4. Marathon programmes in the book

- Chapter 14 offers six options (Table 14.1, pp. 314-315): Basic (3 to 5 days a week, for new or returning runners), 2Q, the 4-week cycle, the 5-week cycle, the last 18 weeks, the last 12 weeks.
- 2Q (p. 319): run at least 6 weeks first; two Q sessions a week; train at least 6 days a week.
- Training VDOT in the 2Q programme (p. 320): for the first 6 weeks use a VDOT 2 units below the estimated marathon VDOT, then add 1 unit for each following 6 weeks.
- The Basic programme is for new or returning runners (pp. 315-316). The book does not set a time target for it; reading it as "aimed at finishing" is our inference.

## R5. Feasibility of FM sub 4:00 and sub 3:45

Computed with `app/vdot.py`:

| Target | VDOT needed | Book table value |
|---|---|---|
| Sub 3:45 | about 41.0 (3:44:59) | VDOT 41 is 3:45:09, VDOT 42 is 3:40:43 |
| Sub 4:00 | about 38 | VDOT 38 is 3:59:35 |

Decisions from this: sub 4:00 stays in scope (the ceiling in `specs/mission.md` is 3:59:00); sub 3:45 stays out of scope until the weekly-distance check below exists.

## R6. Web evidence from amateur runners (searched 2026-11-13)

All of it is anecdotal. No source reports a runner reaching sub 4:00 or sub 3:45 by following Daniels closely, and no study tests VDOT on low-mileage runners.

- Running with Rock, 2Q pros and cons (https://runningwithrock.com/marathon-training-plan-jd-2q/): one runner's review. The 55 miles-a-week plan needs 45 miles a week run comfortably first; at 40 miles a week the Q sessions leave little easy running; not for beginners. No finish time given.
- Running Ahead, Daniels marathon plan on lower mileage (https://www.runningahead.com/forums/post/0463e72dcea04df7bdfbf410c429492c): posters think it works at about 50 to 60 miles a week. One poster's half marathon of 1:33:48 (VDOT 48.6) sat beside a marathon of 4:13:43 (VDOT 35.4), which shows VDOT over-predicting the marathon for that runner. The thread does not say the marathon used the Daniels plan.
- Slowtwitch, 2007 (https://forum.slowtwitch.com/t/question-re-jack-daniels-marathon-program/386094): one experienced runner found the paces "honest and difficult" and M pace unrealistic for casual runners; they raced about 15 seconds a mile slower than M pace.
- Slowtwitch, 2Q experience (https://forum.slowtwitch.com/t/jack-daniels-2q-marathon-plan-experience/783088): a triathlete on 40 to 80 km a week, no marathon result reported.
- Runner's World South Africa (https://www.runnersworld.co.za/training/i-broke-4-hours-in-the-marathon-thanks-to-these-training-tweaks/): 4:33 to 3:49 over three years on the magazine's Break 4 Hours plan, peak week about 65 km. Daniels is not mentioned. Useful only as a volume reference.
- Frontiers in Physiology 2025 (https://www.frontiersin.org/articles/10.3389/fphys.2025.1718298): 7,663 Valencia runners; VDOT predicted the marathon from the half marathon with a mean absolute error of 7.9%, against 5.7% for the authors' regression model. VDOT did better for the fastest runners. About 18 minutes of error on a 3:45 marathon, as an average, not a bound.

## Decisions taken from this research

- A missed Quality workout is dropped, not made up. Lost distance goes to the remaining Easy runs, within Weekly availability and the Long run limit, and the runner confirms.
- A week never exceeds its Weekly volume.
- For a marathon Goal, check recent weekly distance (about 64 km) before choosing between a 2Q-style and a Basic-style plan, and warn when VDOT comes from a race shorter than a half marathon. The 64 km figure is our inference from the 2Q material and the Running with Rock review; the book does not state it.
- Gaps between this research and the code are listed in the session summary and need their own issues.
