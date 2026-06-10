# FAQ — plain-language guide

This page assumes no shipping background *and* no software background. Pick the section that matches you.

---

## The problem, in one paragraph

Every commercial ship files a "noon report" each day at sea — a short record of position, speed, distance run, weather, and fuel burned. Locked inside that humble daily record are two of the most expensive questions in ship operation: *is the hull getting dirty?* (a fouled hull drags, and drag is paid for in fuel — easily hundreds of thousands of dollars a year per ship) and *what carbon grade will the regulator give this ship?* (the IMO's CII rating, A–E, with commercial and regulatory consequences below C). The analysis that answers both questions has historically lived inside expensive proprietary platforms. noonkit is the open, auditable version: upload noon reports, get the fouling signal and the CII rating, and read exactly how every number was produced.

---

## I'm a software person with no shipping background

Five concepts and you understand the whole tool:

1. **A noon report is a daily, hand-entered log row.** Speed over ground, distance run in 24 hours, fuel consumed by fuel type, weather (Beaufort scale), drafts. It's messy, real-world data — typos, unit slips, impossible values — which is why noonkit's ingestion layer attaches quality flags rather than silently "fixing" anything.
2. **Fuel consumption rises steeply with speed.** Resistance through water grows roughly with the cube of speed, so a ship has a characteristic speed–consumption curve. Fit that curve from the data and you have a model of what the ship *should* burn at any speed.
3. **Hull fouling is drift away from that curve.** Marine growth on the hull adds drag, so the ship gradually burns more fuel than the curve predicts *at the same speed*. The fouling signal is exactly that: the percentage gap between actual and predicted consumption, trending upward over months. No sensor needed — the signature is in data the ship already files daily.
4. **Weather is the confounder, so it's filtered.** A gale makes any hull burn more. The baseline is therefore fitted on good-weather reports only (Beaufort ≤ 4 by default), and on the *early* part of the record — fitting across the whole series would average the fouling into the baseline and hide the very thing being measured.
5. **CII is a regulated efficiency grade, computed not estimated.** Attained CII = CO₂ emitted ÷ (capacity × distance sailed). It's compared against a ship-type reference line and a yearly tightening factor from IMO resolutions, then placed into A–E bands. There's no model here — it's regulation arithmetic, implemented straight from the MEPC texts and pinned by tests, which is what makes it auditable.

The architecture follows from this: all calculation lives in the Python library; the Streamlit dashboard computes nothing of its own, so the UI can never silently disagree with the tested engine. Start reading at the library's CII module and `imo_reference.py`, where every numeric table cites the resolution it came from.

## I'm a mariner with no software background

You don't need to touch any code. The tool runs in your web browser:

1. Open the live app (noonkit.streamlit.app). It's a normal web page.
2. Export or assemble your noon reports as a CSV — one row per day, with columns for date, speed, distance, fuel consumed, and weather. The app maps common column-name variations automatically and the repository includes an example file showing the expected shape.
3. Upload the CSV, choose the ship type and capacity (DWT or GT, as appropriate for the type), and the year.
4. Read the two outputs. **Performance:** the speed–consumption curve, the clean-hull baseline, and the deviation trend — a persistently rising deviation, in good weather, is the operational signature of fouling or machinery degradation, and it's expressed in percentage points per 30 days so you can act on it (timing a hull clean, briefing the superintendent). **CII:** attained vs required, and the A–E letter.
5. Mind the flags. Rows with implausible values (speed–distance mismatches, impossible consumption) are flagged, not deleted — you decide whether to exclude them, and the default keeps them out of the trend so one bad entry can't fake a fouling signal.

What it is and isn't: noonkit gives **planning estimates and early warning**, not a verified Statement of Compliance — ratings are issued by your Administration or RO against verified DCS data. Use it the way you'd use a good superintendent's spreadsheet, with the working shown.

---

## Common questions

**How much does fouling actually cost? Why should I care about a few percent?**
A modest 2% rise in speed–power deviation on an Aframax-class tanker is roughly 2.4 t of extra fuel per day at sea. Over 300 sea days at typical bunker prices, that's on the order of half a million dollars per ship per year — before counting the EU ETS bill on the extra CO₂ and the CII erosion. Fouling develops slowly and invisibly; the entire point of trending the deviation is to see it months before dry dock makes it obvious.

**Why fit the baseline on only the first 30 days?**
Because the baseline must represent the *clean* hull. If you fit it across the whole record, the later, fouled months pull the curve up and the deviation you wanted to measure disappears into the reference. The window is configurable; what matters is that it precedes the period you're judging.

**Why exclude bad-weather reports?**
A single Beaufort 7 day can burn more excess fuel than a month of light fouling. Filtering to Beaufort ≤ 4 keeps the comparison like-for-like, so the trend reflects the hull, not the North Atlantic.

**Where do the CII numbers come from? Can I check them?**
Every coefficient is in `imo_reference.py` with the resolution it came from (reference-line a/c parameters, reduction factors, rating dd-vectors, fuel→CO₂ conversion factors). The verification pass against the original IMO PDFs caught — and fixed — two transcription errors that circulate in secondary sources, which is precisely why the audit exists. See [VERIFICATION.md](VERIFICATION.md).

**My ship got a different rating from my class society's tool. Who's wrong?**
Possibly neither. Differences usually come from voyage correction factors (MEPC.355(78)) — which noonkit deliberately does not apply — or from data scope (verified DCS data vs your raw noon reports). noonkit's figure is the conservative, uncorrected estimate.

**What does the tool deliberately NOT do?**
Voyage adjustments and correction factors; weather *correction* (it filters instead — correcting requires data noon reports don't reliably carry); machinery-level diagnosis (it tells you the ship is off its curve, not which component is responsible); and any compliance certification.

**A figure looks wrong / the regulation changed. What do I do?**
Open an issue on the GitHub repository quoting the primary source. Corrections against primary sources are the point of publishing this openly.

**Can I get help applying this to my fleet?**
noonkit is maintained by [Navallogic Solutions](https://navallogic.com), an independent maritime advisory focused on vessel-performance analytics and decarbonisation compliance. For fleet-wide performance audits, hull-cleaning timing studies, or CII trajectory planning beyond what a public tool can responsibly do, reach out via the website.

---

## Command glossary (for non-developers running it locally)

| You type | What it actually does |
|---|---|
| `git clone <url>` | Downloads a complete copy of the project from GitHub to your computer. |
| `python -m venv .venv` | Creates a private sandbox of Python packages just for this project. |
| `source .venv/Scripts/activate` | Steps your terminal into that sandbox (Windows Git Bash). The prompt shows `(.venv)` when you're in. |
| `pip install -e .` | Installs noonkit itself into the sandbox, in "editable" mode so the code you see is the code that runs. |
| `python -m pytest -q` | Runs the automated checks that verify the maths against IMO worked examples. |
| `streamlit run app.py` | Starts the dashboard in your browser at `localhost:8501`. `Ctrl+C` stops it. |

---

*Maintained by [Navallogic Solutions](https://navallogic.com) · See also: [METHODOLOGY.md](METHODOLOGY.md) for the formulas, [VERIFICATION.md](VERIFICATION.md) for the audit of every constant against its source. Companion tools: [FuelEU Pool Optimiser](https://github.com/rizwanalimondal/fueleu-pool-optimiser) · [Maritime GHG Compliance Navigator](https://github.com/rizwanalimondal/ghg-compliance-navigator).*
