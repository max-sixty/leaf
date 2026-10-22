Keep the page's summary, checks and log current from the deployment system, rather than
having the browser interpret the log.

A pick of the rollback option requests a rollback, and a later pick can replace it.
Before acting, read the group's current answer with `leaf page state`, and go ahead only
while the rollback option is chosen. Then check in the deployment system that the
candidate the option names still receives traffic, and that its stable release is still
the right target. When you resume after an interruption, look in the deployment system
for an earlier rollback or its result before starting another. When the rollback
completes, is refused or stops partway, update the observations it changed and say what
happened in the stamped version.
