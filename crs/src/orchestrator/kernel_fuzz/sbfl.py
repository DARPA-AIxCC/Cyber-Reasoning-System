import argparse
import glob
import json
import os
import re
import subprocess as sp

import numpy as np
import polars as pl

parser = argparse.ArgumentParser(
    description="Spectrum Based Fault Localization (SBFL) trace analyzer"
)
parser.add_argument(
    "crashdir",
    metavar="<Crashing Traces Dir>",
    help="directory containing crashing traces as addresses",
)
parser.add_argument(
    "bendir",
    metavar="<Non-crashing Traces Dir>",
    help="directory containing benign traces as addresses",
)
parser.add_argument("--topN", "-n", default=10, help="Number of results to report")
parser.add_argument("--outfile", "-o", help="Output file")
parser.add_argument(
    "--tiebreak-files",
    help="Comma separated list of file names to use as scoring tie-breakers",
)
parser.add_argument(
    "--tiebreak-files-path",
    help="Path to json file containing list of tie-breaker files",
)
parser.add_argument(
    "--tiebreak-functions",
    help="Comma separated list of function names to use as scoring tie-breakers",
)
parser.add_argument(
    "--tiebreak-functions-path",
    help="Path to json file containing list of tie-breaker function",
)
parser.add_argument(
    "--experiment_dir", "-e", help="Experiment directories to track true sources"
)
parser.add_argument("--binary", "-b", help="Origianl binary file path")
parser.add_argument(
    "--algorithm", "-a", default="ochiai", choices=["ochiai"], help="SBFL algorithm"
)
args = parser.parse_args()

topN_num = int(args.topN)

# def process

experiment_directories = []

if args.experiment_dir is not None:
    experiment_directories += args.experiment_dir.split(",")


def parse_file(fname):
    df = (
        pl.read_csv(fname, has_header=False, new_columns=["address"])
        .group_by("address")
        .count()
    )
    df = df.select("count").transpose(column_names=df["address"])

    df = df.cast(pl.UInt32)
    df = df.select(sorted(df.columns))
    return df


def traces_to_df(dirname_a, dirname_b, crashing_name) -> pl.DataFrame:
    crashing_trace_fnames = glob.glob(f"{dirname_a}/*")
    non_crashing_trace_fnames = glob.glob(f"{dirname_b}/*")

    crashing_traces = []
    for fname in crashing_trace_fnames:
        print(fname)
        try:
            crashing_traces += [parse_file(fname)]
        except Exception:
            print(f"failed to read {fname}")

    crashing_df = pl.concat(crashing_traces, how="diagonal").with_columns(
        pl.lit(True).alias(crashing_name)
    )

    non_crashing_traces = []
    for fname in non_crashing_trace_fnames:
        print(fname)
        try:
            non_crashing_traces += [parse_file(fname)]
        except Exception:
            print(f"failed to read {fname}")
    non_crashing_df = pl.concat(non_crashing_traces, how="diagonal").with_columns(
        pl.lit(False).alias(crashing_name)
    )
    df = pl.concat([non_crashing_df, crashing_df], how="diagonal")
    cols = df.columns
    cols.remove(crashing_name)
    df = df.select([crashing_name] + sorted(cols))
    df = df.fill_null(0)
    return df


crashing_name = os.path.basename(args.crashdir.rstrip("/"))
out_dir = os.path.commonprefix(
    [os.path.abspath(args.crashdir), os.path.abspath(args.bendir)]
)
df = traces_to_df(args.crashdir, args.bendir, crashing_name)

df = df > 0

counts = df.group_by(crashing_name).count()

total_failing = counts.filter(pl.col(crashing_name))["count"][0]
total_passing = counts.filter(~pl.col(crashing_name))["count"][0]

print("")
print("total crashing traces:")
print(total_failing)
print("total non-crashing traces:")
print(total_passing)

efs = df.filter(pl.col(crashing_name)).drop(crashing_name).sum()
eps = df.filter(~pl.col(crashing_name)).drop(crashing_name).sum()
nfs = ((df.filter(pl.col(crashing_name)).drop(crashing_name)) == False).sum()  # noqa
nps = ((df.filter(~pl.col(crashing_name)).drop(crashing_name)) == False).sum()  # noqa

ochiai: pl.DataFrame

ochiai = efs / ((total_failing) * (efs + eps)).map_rows(np.sqrt)

scores = ochiai.transpose(
    include_header=True, header_name="address", column_names=["score"]
)
# scores = scores.with_columns(
#      pl.col("file_line").str.split(":").list.get(1).cast(pl.UInt32).alias("line"),
#      pl.col("file_line").str.split(":").list.get(0).alias("file")
# )

scores = scores.sort("score", descending=True)
print("Calculated and sorted scores")

if args.outfile is None:
    outfile = f"{out_dir}/{args.algorithm}.json"
else:
    outfile = args.outfile

all = scores
all.write_json(f"{outfile}.all")


print("")
print(f"Ochiai Top-{args.topN}")

pseudo_blocks = {}

grouping = (pl.arange(0, scores.height)) // 1000  # Process in groups of 1000

llvm_line_extractor = (
    "llvm-symbolizer-14 --output-style=GNU --no-inlines -C"
)
gcc_line_extractor = "addr2line"

builders = sp.run(
    f"readelf -p .comment {args.binary}",
    stdout=sp.PIPE,
    stderr=sp.PIPE,
    shell=True,
    executable="/bin/bash",
)

print(f"Found builder info {builders}")

line_extractor = gcc_line_extractor

if builders.returncode == 0 and "clang" in builders.stdout.decode("utf-8"):
        line_extractor = llvm_line_extractor

print(f"Line extractor is {line_extractor}")

for name, group in scores.with_columns(group=grouping).group_by("group"):
    address_list = " ".join(list(group.select("address").to_series()))
    location_info = sp.run(
        f"{line_extractor} -e {args.binary} -p -f {address_list}",
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        shell=True,
        executable="/bin/bash",
    )

    for stdout_line, score in zip(
        location_info.stdout.decode("utf-8").split("\n"),
        list(group.select("score").to_series()),
    ):
        if score == 0:
            continue
        if "??" in stdout_line:
            continue
        # print(stdout_line)

        m = re.match("(.*) (.* )?at (.*?:\d+)(:\d+)?", stdout_line)
        if not m:
            continue
        func = m.group(1)

        file_line = m.group(3)

        (file, executable_line) = file_line.split(":")

        if experiment_directories:
            found = False
            for experiment_dir in experiment_directories:
                if experiment_dir in file:
                    found = True
                    file = file[file.index(experiment_dir)+len(experiment_dir)+1:]
                    break
            if not found:
                continue

        if executable_line == "?":
            continue
        else:
            executable_line = int(executable_line)

        if file not in pseudo_blocks:
            pseudo_blocks[file] = {}

        target_block = pseudo_blocks[file]
        target_block_key = (score, func)

        if target_block_key not in target_block:
            target_block[target_block_key] = [
                range(executable_line, executable_line + 1)
            ]
        else:
            add = False
            for i, pseudo_block_range in enumerate(target_block[target_block_key]):
                # print(f"Compare {executable_line} {pseudo_block_range.stop}")
                # print(target_block[target_block_key])
                # input()
                if (
                    executable_line >= pseudo_block_range.stop
                    and executable_line <= pseudo_block_range.stop + 10
                ):  # extend from right
                    target_block[target_block_key][i] = range(
                        pseudo_block_range.start, executable_line + 1
                    )
                    add = False
                elif (
                    executable_line >= pseudo_block_range.start - 5
                    and executable_line <= pseudo_block_range.start
                ):  # extend from left
                    target_block[target_block_key][i] = range(
                        executable_line, pseudo_block_range.stop
                    )
                    add = False
                elif executable_line in pseudo_block_range:
                    add = False
                else:
                    add = True
            if add:
                target_block[target_block_key].append(
                    range(executable_line, executable_line + 1)
                )

updated_ranges = {}

# pprint(pseudo_blocks)
# input()

tiebreak_files = []
if args.tiebreak_files is not None:
    tiebreak_files = args.tiebreak_files.split(",")
if args.tiebreak_files_path is not None:
    with open(args.tiebreak_files_path, "r") as f:
        tiebreak_files += json.load(f)

for depth, tiebreak_file_line in enumerate(tiebreak_files):
    file, executable_line = tiebreak_file_line.split(":")
    executable_line = int(executable_line)
    updated_distribution = {}
    # pprint(pseudo_blocks[file])
    # input()
    file_increment = 0.0001 - depth * 0.000005
    if file in pseudo_blocks:
        for (score, func), ranges in pseudo_blocks[file].items():
            for i in range(len(ranges)):
                new_score = score + file_increment
                if executable_line in ranges[i]:
                    new_score += (0.00001 - depth * 0.0005)
                if (new_score, func) not in updated_distribution:
                    updated_distribution[(new_score, func)] = []
                updated_distribution[(new_score, func)].append(ranges[i])
        pseudo_blocks[file] = updated_distribution
    # pprint(pseudo_blocks[file])
    # input()

tiebreak_functions = []
if args.tiebreak_functions is not None:
    tiebreak_functions = args.tiebreak_functions.split(",")
if args.tiebreak_functions_path is not None:
    with open(args.tiebreak_functions_path, "r") as f:
        tiebreak_functions += json.load(f)


for depth, tiebreak_function in enumerate(tiebreak_functions):
    function_increment = 0.0001 - depth * 0.000005
    new_blocks = {}
    for file, clusters in pseudo_blocks.items():
        new_blocks[file] = {}
        for (score, func), ranges in clusters.items():
            if func == tiebreak_function:
                new_score = score + function_increment
            else:
                new_score = score
            new_blocks[file][(new_score, func)] = ranges
    pseudo_blocks = new_blocks

updated_pseudo_blocks = {}
for file, clusters in pseudo_blocks.items():
    updated_pseudo_blocks[file] = {}
    for (score, func), ranges in clusters.items():
        ranges.sort(key=lambda r: r.start)

        new_ranges = [ranges[0]]

        for i in range(1, len(ranges)):
            if ranges[i].start in new_ranges[-1]:
                new_ranges[-1] = range(
                    new_ranges[-1].start, max(new_ranges[-1].stop, ranges[i].stop)
                )
            else:
                new_ranges.append(ranges[i])
        updated_pseudo_blocks[file][(score, func)] = new_ranges

pseudo_blocks = updated_pseudo_blocks

res = []
for file, clusters in pseudo_blocks.items():
    for (score, func), ranges in clusters.items():
        for block_range in ranges:
            res.append(
                {
                    "source_file": file,
                    "line_numbers": list(block_range),
                    "score": score,
                    "function": func,
                }
            )

res.sort(key=lambda x: x["score"], reverse=True)

with open(f"{out_dir}/ochiai_all.csv", "w") as f:
    for entry in res:
        f.write(
            f"{entry['source_file']},{entry['line_numbers'][0]}-{entry['line_numbers'][-1]},{entry['score']},{entry['function']}\n"
        )


with open(f"{out_dir}/ochiai.csv", "w") as f:
    for entry in res[:topN_num]:
        f.write(
            f"{entry['source_file']},{entry['line_numbers'][0]}-{entry['line_numbers'][-1]},{entry['score']},{entry['function']}\n"
        )

with open(outfile+".full", "w") as f:
    json.dump(res, f)
    
with open(outfile, "w") as f:
    json.dump(res[:topN_num], f)
    
