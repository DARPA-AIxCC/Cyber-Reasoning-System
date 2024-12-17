import subprocess as sp
import os
import shutil
import random
import glob
import math
import numpy as np
import sys
import json
import time
import tlsh
from multiprocessing import Queue
import watchdog
from watchdog.events import FileSystemEvent
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEvent
from watchdog.events import FileCreatedEvent
from watchdog.events import FileSystemEventHandler
from os.path import join

f = open(sys.argv[1])
md = json.loads(f.read())
f.close()

cp_path = md["cp_path"]

name = md["harnesses"][0]["name"]

timeout = os.getenv("HT_TIMEOUT")
if timeout is None:
    timeout = "1s"

cli = f"timeout -k 5s {timeout} {cp_path}/run.sh run_pov @@ {name}"

initial_corpus_dir = join(md["output_dir_abspath"],"in")
# @TODO watch/monitor dir
working_corpus_dir = join(md["output_dir_abspath"],"corpus")
crash_corpus_dir = join(md["output_dir_abspath"], "crashes")
benign_dir = join(md["output_dir_abspath"], "queue")

annealing = 1
num_crashes = 0
num_corpus = 0
num_executions = 0
last_addition = 0
thresh = 1

def print_log(s):
    print(
        f"{{execs: {num_executions}, corpus: {num_corpus}, crashes: {num_crashes}}} --- {s}"
    )


if os.path.exists(working_corpus_dir):
    shutil.rmtree(working_corpus_dir)

os.makedirs(initial_corpus_dir, exist_ok=True)
os.makedirs(benign_dir, exist_ok=True)

if len(os.listdir(initial_corpus_dir)) == 0:
    sp.run(f"echo 'hi' > {initial_corpus_dir}/hi.txt", shell=True)
    sp.run(f"echo 'bye' > {initial_corpus_dir}/bye.txt", shell=True)
    sp.run(f"echo 'halo' > {initial_corpus_dir}/halo.txt", shell=True)

os.makedirs(working_corpus_dir)
os.makedirs(crash_corpus_dir, exist_ok=True)

sp.run(f"bash -c 'cp {initial_corpus_dir}/* {working_corpus_dir}/'", shell=True)

queue = Queue()
files = glob.glob(f"{working_corpus_dir}/*")
for f in files:
    queue.put((f, 1))

def mutate_chunk(chunk, num_bytes):
    op = random.choice(range(20))

    ex = False
    while not ex:
        try:
            r = random.randint(0, 2 ** (num_bytes * 8))
            new_bytes = (r).to_bytes(byteorder="big", length=num_bytes)[0:num_bytes]
            ex = True
        except:
            continue

    try:
        if op == 1:
            new_bytes = bytes.fromhex("000000000000000000000000")[0:num_bytes]
        elif op == 2:
            new_bytes = bytes.fromhex("ffffffffffffffffffffffff")[0:num_bytes]
        elif op == 3:
            x = int.from_bytes(chunk, byteorder="big")
            new_bytes = (x + 1).to_bytes(byteorder="big", length=num_bytes)
        elif op == 4:
            x = int.from_bytes(chunk, byteorder="little")
            new_bytes = (x + 1).to_bytes(byteorder="little", length=num_bytes)
        elif op == 5:
            x = int.from_bytes(chunk, byteorder="big")
            new_bytes = (x - 1).to_bytes(byteorder="big", length=num_bytes)
        elif op == 6:
            x = int.from_bytes(chunk, byteorder="little")
            new_bytes = (x - 1).to_bytes(byteorder="little", length=num_bytes)
        elif op == 7:
            x = int.from_bytes(chunk, byteorder="little")
            new_bytes = (x).to_bytes(byteorder="big", length=num_bytes)
        elif op == 8:
            new_bytes = mutate_chunk(chunk + chunk, num_bytes * 2)
        elif op == 9:
            new_bytes = mutate_chunk(chunk + chunk + chunk, num_bytes * 3)
        elif op == 0:
            new_bytes = mutate_chunk(chunk + chunk + chunk + chunk, num_bytes * 4)
        elif op == 11:
            new_bytes = mutate_chunk(
                chunk + chunk + chunk + chunk + chunk + chunk + chunk + chunk,
                num_bytes * 8,
            )
        elif op == 10:
            new_bytes = b""

    except Exception:
        pass

    print_log(f"\t{op}: {chunk} ---> {new_bytes}")
    return new_bytes


def mutate_file(next):
    mutation_size_bytes_options = [1, 2, 4, 8, 16, 32]
    alignment_options = [0, 1, 2, 3]

    f_size_bytes = os.stat(next).st_size

    alignment = random.choice([o for o in alignment_options if o < f_size_bytes])
    mutation_size_bytes = random.choice(
        [o for o in mutation_size_bytes_options if o < (f_size_bytes - alignment)]
    )
    num_mutations = int(
        min(annealing, (f_size_bytes - alignment) / mutation_size_bytes)
    )
    mutation_indices = random.sample(range(f_size_bytes - alignment), num_mutations)

    byte_index = 0
    with open(next, "rb") as f_og:
        with open(join(md["output_dir_abspath"],".input"), "wb") as f_new:
            while byte := f_og.read(1):
                if byte_index + alignment in mutation_indices:
                    print_log(
                        f"Mutating {mutation_size_bytes} bytes @{byte_index + alignment}"
                    )
                    chunk = byte
                    for i in range(mutation_size_bytes - 1):
                        byte = f_og.read(1)
                        byte_index += 1
                        chunk += byte

                    chunk = mutate_chunk(chunk, mutation_size_bytes)
                    f_new.write(chunk)
                else:
                    f_new.write(byte)
                byte_index += 1


def pad(array, target_shape):
    return np.pad(
        array,
        [(0, target_shape[i] - array.shape[i]) for i in range(len(array.shape))],
        "constant",
    )

coverage = {}

def score_lsh(o):
    global thresh
    global coverage

    current = tlsh.hash(o)
    print(f"Hash {current}")

    if len(coverage.keys()) == 0:
        coverage[current] = 1
        return (1, 1)

    max_diff = thresh
    for (h, ct) in coverage.items():
        diff = tlsh.diff(current, h)
        print(f"Diff was (of {thresh}):")
        print(f"\t{diff}")
        if diff < thresh:
            coverage[h] += 1
            return (0, coverage[h])
        max_diff = max(max_diff, diff)
    n = len(coverage.keys())
    thresh = int(
        thresh*n/(n+1) 
            + (max_diff/n+1))

    coverage[current] = 1
    return (1, 1)


NONCE = "@@@~~~"


def score(o):
    global coverage
    input_score = 0

    N = 5
    lines = [l.split(NONCE)[1] for l in o.splitlines() if NONCE in l]

    # add padding
    lines = ["0"] * N + lines
    lines = lines + ["0"] * N

    for i in range(0, len(lines) - N):
        buf = lines[i : (i + N)]
        h = hash(tuple(buf))
        if h not in coverage:
            coverage.add(h)
            input_score = 1

    return input_score


def has_crash(o):
    for sanitizer in md["sanitizers"]:
        if sanitizer["name"] in o:
            return True


in_path = join(md["output_dir_abspath"],'.input')

additional_seeds = (
    join(os.getenv("AIXCC_CRS_SCRATCH_SPACE"), "peach", md["subject"], md["bug_id"], "")
    if os.getenv("AIXCC_CRS_SCRATCH_SPACE", None)
    else ""
)

if additional_seeds:
    os.makedirs(additional_seeds,exist_ok=True)

class FileCreationHandler(FileSystemEventHandler):
    def on_created(self, event: FileSystemEvent) -> None:
        print_log(f"Got external input {event.src_path}")
        queue.put((event.src_path, 1))

if additional_seeds and os.path.exists(additional_seeds):
    observer = Observer()
    observer.schedule(FileCreationHandler(),additional_seeds)
    observer.start()

def run_and_score(in_path):
    global num_crashes

    print_log("running....")
    p = sp.run(f"{cli.replace('@@', in_path )}", shell=True, capture_output=True)

    output = p.stdout.decode("utf-8", errors="ignore") + p.stderr.decode(
        "utf-8", errors="ignore"
    )
    # x = output.splitlines()[-50:]
    # print("...")
    # print("\n".join(x))

    if has_crash(output):
        sp.run(f"cp {in_path} {crash_corpus_dir}/crash_{int(time.time())}", shell=True)
        num_crashes += 1
    else:
        sp.run(f"cp {in_path} {benign_dir}/ben_{int(time.time())}", shell=True)

    return score_lsh(p.stdout + p.stderr)

def get_power(ct_old):
    global num_executions

    if num_executions == 0:
        prob = 1
    else:
        prob = (num_executions - ct_old) / (num_executions)  

    power = int(prob * 10)

    if power == 0:
        if random.random() < prob * 10:
            power = 1
        else:
            power = 0

    return power


while num_executions < 5000000:
    (next, ct_old) = queue.get()

    power = get_power(ct_old)

    re_count = 0
    for i in range(power):
        try:
            mutate_file(next)
            (s, ct_new) = run_and_score(in_path)
        except KeyboardInterrupt as e:
            raise e
        except:
            queue.put((next, ct_old + 1))
            continue

        if s > 0:
            sp.run(f"cp {in_path} {working_corpus_dir}/{num_executions}.in", shell=True)
            queue.put( (f"{working_corpus_dir}/{num_executions}.in", 1) )
            num_corpus += 1
            last_addition = 0
            print_log("new input added!")

        if last_addition > 100:
            annealing += 1
            annealing = annealing % 100
            last_addition = 0

        num_executions += 1
        last_addition += 1
        re_count += ct_new

    queue.put((next, re_count))

