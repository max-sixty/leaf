The page's summary, checks, and log describe the observed release. Keep them current
from the deployment system rather than interpreting the log in the browser.

A pick of the rollback option asks for a rollback; it has not happened yet, and a
later pick can replace it. Before acting, read the group's current answer in
`leaf page state` and proceed only while the rollback option stands, then verify
that the candidate the option names is still receiving traffic and that its stable
release is still the intended rollback target. On recovery, the deployment system is
where to look for an earlier rollback or its result before starting another. Once the
rollback completes, or the deployment system refuses it or it stops short, refresh
the release observations the result changes and say in the stamped version what
happened.
