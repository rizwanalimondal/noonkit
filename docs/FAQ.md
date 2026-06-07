# FAQ — noonkit in plain language

A plain-English companion to the code. If you're new to the project (or to
maritime data, or to Python), start here. For the formula-by-formula detail,
see [METHODOLOGY.md](METHODOLOGY.md).

---

## What problem does noonkit solve?

Every ship writes down, once a day at noon, how fast it went, how much fuel it
burned, the weather, and how far it travelled. That daily note is called a
**noon report**, and ships have filed them for over a century.

Hidden in those notes are answers to two expensive questions:

1. **Is the hull getting dirty?** Barnacles and slime grow on a ship's
   underwater body over time ("fouling"). A dirty hull drags, so the engine
   burns more fuel for the same speed. It creeps up slowly and quietly inflates
   fuel bills.
2. **Will the ship pass its carbon grade?** The IMO (International Maritime
   Organization, a UN body) gives big ships an annual A–E grade for carbon
   emitted per unit of cargo moved. This is the **CII** (Carbon Intensity
   Indicator). A D or E forces corrective action plans, so operators want to
   know their grade *before* year-end.

Tools that answer these exist — but they're locked inside expensive commercial
software. **noonkit answers both, for free, from a ship's own noon reports.**

---

## How is it built? (the factory analogy)

noonkit is a small factory. Messy noon reports go in one end; useful answers
come out the other. Each "station" is one Python file:

| Station | File | What it does |
|---|---|---|
| The Translator | `ingest.py` | Maps each company's messy column names ("Speed", "Obs Speed", "SOG"…) onto one standard set noonkit understands. Acts as a quality inspector: flags impossible rows (negative distance, 999 t/day fuel) but never silently deletes or "fixes" data — it tells you, your call. |
| The Fuel Detective | `performance.py` | Learns the ship's healthy speed-vs-fuel pattern from its early, clean, good-weather days, then checks whether later days burn more than that healthy pattern predicts. Steady excess over months = fouling fingerprint. |
| The Rule Book | `imo_reference.py` | A careful, labelled copy of the IMO's official number tables for the CII grade. Every number says which IMO document it came from. |
| The Grader | `cii.py` | Runs the IMO's official formula to produce the attained CII, the required CII (target), and the A–E grade — showing all its working so the grade can be audited. |
| The Front Desk | `cli.py` | Lets you run the whole factory with one typed command (`noonkit analyze reports.csv`) instead of writing code. |

Plus:

- **`tests/`** — 32 automatic self-checks that prove the code does what we
  claim (see below).
- **`examples/`** — realistic *fake* noon data (real data is private) with a
  hidden fouling signal baked in, so the tool can be shown rediscovering it,
  plus the scripts that make the demo charts.

---

## Why should anyone trust the numbers?

Because they were checked against the source, and the checks are automated.

- The IMO publishes a **worked example** ("a bulk carrier with these inputs
  should get grade B"). A test runs our code on those exact inputs and confirms
  it returns B. If the math ever broke, that test would fail loudly.
- Every CII coefficient was verified **line by line against the official IMO
  resolution PDFs** (MEPC.353(78) and MEPC.354(78)).
- That verification **caught two wrong numbers** we'd inherited from a secondary
  source:
  1. An **LNG carrier** size-band coefficient was wrong and the bands were
     grouped incorrectly.
  2. A **vehicle carrier** coefficient was simply wrong (we had 5739; the IMO
     document says 3627).
  Both are now fixed and pinned with tests so they can't regress.

This is the honest version of "how do I know it's right": *it was verified
against primary sources, that caught real errors, and the correct values are
locked in by automated tests.*

---

## What does it deliberately NOT do? (known limits)

Being upfront about limits is part of being trustworthy:

- It computes the **uncorrected** CII. The IMO allows some ships "correction
  factors" (e.g. discounts for ice voyages, ship-to-ship operations). Those
  aren't built yet, so for eligible ships our grade is slightly *pessimistic*.
  On the roadmap.
- It is a **decision-support tool, not an official compliance certificate.**
  Real grades are issued by Administrations / Recognized Organisations against
  verified data. noonkit helps you estimate and plan.
- The fouling model is deliberately simple (no trim/draft correction yet).
- Reduction factors beyond 2026 aren't finalised by the IMO; where the tool
  projects past 2026 it labels the result an *unofficial projection* rather than
  presenting it as settled regulation.

---

## Glossary of the commands used to ship this

For anyone following the setup steps who's new to a terminal.

**`git`** — saves snapshots of your project and syncs them to GitHub (think:
"save to the cloud, with full history").
- `git status` — "what have I changed?"
- `git add .` — "mark all my changes to be saved" (`.` = everything here)
- `git commit -m "note"` — "save a snapshot, with a describing note"
- `git push` — "send my snapshots up to GitHub"
- `git pull` — "bring down changes on GitHub I don't have locally"

**`python`** — runs the Python language.

**`pip`** — Python's app store; downloads/installs code packages (e.g. pandas
for tables). `pip install pandas` = fetch and install pandas.

**`pytest`** — runs the test suite (the 32 self-checks).

**The little flags:**
- **`-m`** — "run a module *through* Python." `python -m pip` runs pip via
  Python. This is the reliable way to run pip/pytest even when the bare command
  isn't found on the system path.
- **`-e`** — "editable." `pip install -e .` installs the package straight from
  this folder, so code edits take effect immediately. (This is what fixes a
  "No module named noonkit" error — it tells Python where noonkit lives.)
- **`-v`** — "verbose." `pytest -v` lists every test name and result instead of
  just a summary.
- **`.`** (single dot) — "the current folder, right here."
- **`-` vs `--`** — one dash for short flags (`-v`, `-m`, `-e`), two dashes for
  full-word flags (`--version`, `--no-rebase`).
- **`cd`** — "change directory" — walk into a folder. **`ls`** — list the files
  in the current folder.

A simple way to remember it: `git` is for **saving and sharing** your work;
`python` / `pip` / `pytest` are for **running and testing** your code; the small
flags just tweak how a command behaves.
