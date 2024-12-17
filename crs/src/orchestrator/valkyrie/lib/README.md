Run:

        $ ./build.sh
        $ ./sum 1 2 3

Should print "6".

        $ ./sum.patched 1 2 3

Should print "-6"

Also try:

        $ PATCH_DEBUG=1 ./sum.patched 1 2 3

for more detailed logging.

