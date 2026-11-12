# toolkit

Small utility library used by the bug-fix swarm demo. Each module under `src/`
has a known bug and a test file under `test/` that exposes it. The test files
and package.json are protected resources in the demo: agents must fix `src/`.
