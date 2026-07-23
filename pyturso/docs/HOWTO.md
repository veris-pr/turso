# HOWTO — docs

How documentation work happens (structure and house rules: [README.md](README.md)).

1. Docs are **phase deliverables**: PLAN.md lists what each phase must
   produce; a phase is not done without them.
2. During Rust reading (working-method step 1), log every question you cannot
   answer in the target module's explanation quadrant as a stub note — these
   stubs are the backlog of explanation docs.
3. Write in the quadrant the *reader's situation* demands (each module tree's
   HOWTO has the decision rule); update the module README status table in the
   same commit.
4. Reference docs update in the same commit as behavior changes. Tutorials
   are end-to-end tested from a clean checkout before committing.
5. After a module works, do the re-read pass (working-method step 5) and
   update the "In Turso" sections with everything the Rust does that the
   port does not.
