The page's summary, checks, and log describe the observed release. Keep them current
from the deployment system rather than interpreting the log in the browser.

A `rollback` request from `lf-release-actions` asks for a rollback; it has not
happened yet. Before acting, verify that the authored `candidate` is still receiving
traffic and that the authored `stable` release is still the intended rollback target.
The delivered request's handling says how to key it and record its receipt. On
recovery, the deployment system is where to look for that request or its result before
sending another rollback. The receipt is the rollback's terminal outcome: write
`succeeded` once the rollback has completed, or `failed` once the deployment system
refuses it or it stops short, and refresh the release observations the result changes.
