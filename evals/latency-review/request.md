# Subject: latency versus throughput — next validation run

Make a review page for these fictional synthetic measurements. I need to compare
throughput against latency, inspect individual runs, and choose which configuration
and worker count to test next under production-like conditions. Recording that choice
plans another validation run; it does not execute a test or deploy anything.

Show throughput on the horizontal axis in requests/second and p99 latency on the
vertical axis in milliseconds. Make all runs identifiable. Let me select a run by
clicking or tapping the chart, or using an ordinary selector, and keep its configuration,
worker count, throughput, p99 and error percentage visible until I select another run.
I also need a keyboard route and a readable phone view. Keep all nine runs available
as exact tabular data alongside the chart or through clearly labeled navigation.

## Measurements

Each cell is one five-minute synthetic run, with no repeats. Configurations A, B and C
are alternative implementations of the same service. Workers are concurrent
load-generator workers; each can have multiple requests in flight, so the worker
count is not a cap on simultaneous requests. Error values below are percentages:
0.04 means 0.04%, not 4%.

| Configuration | Workers | Throughput (requests/s) | p99 latency (ms) | Errors (%) |
| ------------- | ------: | ----------------------: | ---------------: | ---------: |
| A             |       1 |                     680 |              420 |       0.01 |
| A             |       2 |                     980 |              620 |       0.03 |
| A             |       4 |                    1240 |              180 |       0.04 |
| B             |       1 |                     760 |              390 |       0.02 |
| B             |       2 |                    1130 |              590 |       0.04 |
| B             |       4 |                    1380 |              650 |       0.18 |
| C             |       1 |                     820 |              460 |       0.02 |
| C             |       2 |                    1100 |              660 |       0.08 |
| C             |       4 |                    1420 |             1460 |       0.25 |

For this screening exercise, a run is feasible when p99 is at most 700 ms and errors
are at most 0.1%. Prefer the highest throughput among feasible measured runs. Show the
current assessment and why higher-throughput alternatives do or do not qualify.
A single synthetic run per cell provides no repeated-run uncertainty estimate and
establishes neither production performance nor SLO compliance.

Let me choose one of the nine configuration/worker-count combinations for the next
production-like validation and clearly finish recording my choice. Keep inspection
of a run distinct from committing that next-run plan, and keep the measurements and
screening criteria available while I decide.
