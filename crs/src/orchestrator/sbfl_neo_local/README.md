SBFL
====

        $ ./build.sh
        $ ./sbfl-tool instrument prog
        $ ./prog.sbfl < test1
        $ ./prog.sbfl < test2
        $ ...etc.

The `prog` must be compiled with `-g` or else nothing interesting will
happen.

The results are accumulated into `SBFL.prof`.
The file will contain a header, followed by a number of file:line locations,
and an associated score.

The instrumentation automatically considers a non-crashing test as passing,
and a crashing test as failing.

You can also annotate a specific location as "crashing", e.g.:

        $ SBFL_CRASH=file.c:333 ./prog.sbfl < test3

Thus if file.c:333 is execution, then the system will consider the program to
have "crashed" at this point and generate a trace accordingly.
This feature is useful for testing.

You can also annotate a "start" location as follows:

        $ SBFL_START=main.c:777 ./prog.sbfl < test4

This will only start tracing once the specified location is reached.

You can also generate a "full" trace that includes *all* executed lines in
order (the default trace will not repeat lines):

        $ SBFL_DUMP=trace.dump ./prog.sbfl < test5

This could have some useful applications (TBD).

---

The `sbfl-tool` supports the following commands:

* `instrument`: as per above.
* `replace`: like `instrument` but overwrites the original binary.
  The original binary will be backed up into `prog.orig`.

