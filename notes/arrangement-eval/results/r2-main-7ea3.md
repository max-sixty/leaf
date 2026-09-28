| subject | phase | arm | n | gate pass | turns | $ | checks | ✗ reports | CSS lines | JS lines |
|---|---|---|---|---|---|---|---|---|---|---|
| dashboard | 1 | leaf | 3 | 3/3 | 15 | 0.82 | 3 | 0 | 11 | 0 |
| dashboard | 1 | plain | 3 | 3/3 | 15 | 0.75 | 2 | 0 | 29 | 0 |
| dashboard | 2 | leaf | 3 | 3/3 | 9 | 1.10 | 2 | 0 | 17 | 0 |
| dashboard | 2 | plain | 3 | 3/3 | 7 | 0.98 | 2 | 0 | 44 | 0 |
| document | 1 | leaf | 3 | 3/3 | 14 | 0.65 | 2 | 0 | 4 | 0 |
| document | 1 | plain | 3 | 3/3 | 16 | 0.80 | 2 | 0 | 8 | 0 |
| document | 2 | leaf | 3 | 3/3 | 13 | 1.06 | 2 | 0 | 11 | 0 |
| document | 2 | plain | 3 | 3/3 | 9 | 1.17 | 4 | 0 | 18 | 0 |
| queue | 1 | leaf | 3 | 3/3 | 25 | 1.07 | 2 | 1 | 21 | 33 |
| queue | 1 | plain | 3 | 3/3 | 23 | 1.03 | 2 | 0 | 39 | 0 |
| queue | 2 | leaf | 3 | 3/3 | 9 | 1.33 | 3 | 0 | 24 | 33 |
| queue | 2 | plain | 3 | 3/3 | 11 | 1.25 | 2 | 0 | 40 | 0 |

| arm | phase | turns | $ | CSS lines | JS lines | ✗ reports |
|---|---|---|---|---|---|---|
| leaf | 1 | 163 | 7.72 | 125 | 83 | 2 |
| leaf | 2 | 95 | 10.85 | 175 | 83 | 0 |
| plain | 1 | 170 | 7.81 | 210 | 46 | 1 |
| plain | 2 | 79 | 10.48 | 282 | 46 | 0 |

Pairs won in both passes, leaf/plain/split:

| subject | phase | overall | 1440px | 900px | 390px | preference met, leaf and plain, of 2 per pair | discarded |
|---|---|---|---|---|---|---|---|
| dashboard | 1 | 1/2/0 | 1/0/2 | 0/3/0 | 1/0/2 |  | 0 |
| dashboard | 2 | 1/0/1 | 0/0/2 | 1/0/1 | 1/1/0 | 4/4, 4/4 | 1 |
| document | 1 | 1/0/2 | 1/0/2 | 1/0/2 | 0/0/3 |  | 0 |
| document | 2 | 0/1/2 | 0/0/3 | 0/2/1 | 0/1/2 | 6/6, 6/6 | 0 |
| queue | 1 | 3/0/0 | 3/0/0 | 2/0/1 | 1/0/2 |  | 0 |
| queue | 2 | 3/0/0 | 3/0/0 | 2/0/1 | 1/1/1 | 6/6, 6/6 | 0 |
