# HOWTO — api/tutorials

Learning-oriented lessons: the reader follows exact steps and is guaranteed a
working result. Write these **after** the module stabilizes — a tutorial over
churning code rots immediately.

The work:
1. Pick a planned tutorial from the table in [../README.md](../README.md).
2. Choose one concrete artifact the reader builds/sees (a dumped page, a
   stepped program, a recovered WAL) — a tutorial without an artifact is an
   explanation in disguise.
3. Write it as numbered steps with real commands and real expected output.
4. **Test it end to end yourself, from a clean checkout**, before committing.
5. Flip the status in ../README.md to done.

Rules: no options or alternatives mid-flow (link a how-to instead); every
command copy-pasteable; expected output shown after each step.
