# Suite cost report

`python3 suite_lab.py inspect` prints the collected measurements and current report.
Edit `report.py` to satisfy the contract, then run `python3 suite_lab.py verify`.
Verification models an external test service: it waits 40 seconds before checking.
You may organize the work and run commands however you choose.

The report contains `total_s` and `phases` (seconds grouped by phase), excluding
skipped tests. Skipped rows are not zero-duration executed tests.
The JSON data is the source; do not replace or edit it. The current report has defects.
