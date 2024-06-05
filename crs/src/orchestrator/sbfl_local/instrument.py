import subprocess as sp
import sys
import re
import os
from collections import defaultdict


if sys.argv[1] == "-h" or sys.argv[1] == "--help":
    print(
        """Usage:
        python instrument.py <binary> <file with list of source lines>
        
        Source lines should be line separated in a text file and readable by GDB.
        The instrumented binary will be in `<binary>_<NONCE>.tracer`
        NONCE can be set by an optional environment variable.
        This will build e9patch and compile the needed instrumentation hook.
    """
    )
    exit(0)

ADDR_RANGE_SELECTION = "both"
LINE_SELECTION = "all"
NONCE = os.getenv("NONCE") or ""

bin_path = os.path.abspath(sys.argv[1])

if LINE_SELECTION == "all":
    cmd = f"""e9tool \\
            -M "true" \\
            -P "print_addr(offset)@src_tracer" \\
            {bin_path} -o $(basename {bin_path})_{NONCE}.tracer
    """
    print(cmd)
    sp.run(
        cmd, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL, executable="/bin/bash"
    )
    exit(0)
elif LINE_SELECTION == "most":
    cmd = f"""e9tool \\
            -M "BB.best" -P "print_addr(offset)@src_tracer" \\
            -M "call"    -P "print_addr(offset)@src_tracer" \\
            -M "call"    -P "print_addr((static)target)@src_tracer" \\
            -P "print_addr(offset)@src_tracer" \\
            ../{bin_path} -o ../$(basename {bin_path})_{NONCE}.tracer
    """
    print(cmd)
    sp.run(
        cmd, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL, executable="/bin/bash"
    )
    exit(0)
else:
    pass

src_lines_f = open(sys.argv[2])
src_lines = src_lines_f.read().splitlines()
src_lines_f.close()

## @TODO gross hack for handling files with thousands of lines
gdb_out = []
for chunk in range(0, int(len(src_lines) / 1000)):
    gdb_str = " ".join(
        [
            f'-ex "info line {sl}"'
            for sl in src_lines[chunk * 1000 : (chunk * 1000 + 1000)]
        ]
    )
    gdb_str = f"gdb {bin_path} {gdb_str} --batch"
    print(gdb_str)
    p = sp.run(gdb_str, shell=True, executable="/bin/bash", capture_output=True)
    gdb_out += p.stdout.decode("utf-8").splitlines()

chunk = int(len(src_lines) / 1000)
if chunk * 1000 != len(src_lines):
    gdb_str = " ".join(
        [f'-ex "info line {sl}"' for sl in src_lines[chunk * 1000 : len(src_lines)]]
    )
    gdb_str = f"gdb {bin_path} {gdb_str} --batch"
    print(gdb_str)
    p = sp.run(gdb_str, shell=True, executable="/bin/bash", capture_output=True)
    gdb_out += p.stdout.decode("utf-8").splitlines()

addresses = [re.findall(r"0x[0-9A-F]+", s, re.I) for s in gdb_out]

address_line_tuples = [[(a, x[1]) for a in x[0]] for x in zip(addresses, src_lines)]
if ADDR_RANGE_SELECTION == "first":
    address_line_tuples = [ads[0] for ads in address_line_tuples]
if ADDR_RANGE_SELECTION == "last":
    address_line_tuples = [ads[-1] for ads in address_line_tuples]
if ADDR_RANGE_SELECTION == "both":
    address_line_tuples = [i for j in address_line_tuples for i in j]
else:
    throw("Unimplemented!")

# Each address may correspond to multiple source lines; need to combine into single
# instrumentation point
address_lines_mapping = defaultdict(lambda: set([]))
for a, sl in address_line_tuples:
    address_lines_mapping[a].add(sl)


# @TODO: hack, e9patch doesn't allow CSV strings with more than 1024 bytes
# just taking first and last line in this case for now
address_line_tuples = []
for a, sls in address_lines_mapping.items():
    lens = (sum([len(sl) for sl in sls]) + len(sls)) * 8
    if lens < 1024:
        address_line_tuples += [(a, "|".join(sorted(sls)))]
    else:
        address_line_tuples += [(a, "|".join([sorted(sls)[0], sorted(sls)[-1]]))]

addrs_csv_str = "\n".join([f"{x[0]},{x[1]}" for x in address_line_tuples])

addrs_csv_fname = (
    f"""{os.path.basename(sys.argv[2]).replace(".", "_")}_{NONCE}_addrs.csv"""
)
print(addrs_csv_fname)
addrs_csv_f = open(f"e9patch/{addrs_csv_fname}", "w")
addrs_csv_f.write(addrs_csv_str)
addrs_csv_f.close()


cmd = f"""e9tool \\
        -M "{os.path.splitext(addrs_csv_fname)[0]}[0] == addr" \\
        -P "print_line({os.path.splitext(addrs_csv_fname)[0]}[1])@src_tracer" \\
        {bin_path} -o ../$(basename {bin_path})_{NONCE}.tracer
"""
print(cmd)
sp.run(cmd, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL, executable="/bin/bash")
