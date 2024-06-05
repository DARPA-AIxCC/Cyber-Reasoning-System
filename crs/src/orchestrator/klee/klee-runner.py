import sys
import json
import subprocess as sp
import os
from os.path import join
import time

# Read configuration
mdfile = sys.argv[1]
f = open(mdfile)
md = json.loads(f.read())
f.close()


cwd = os.getcwd()
cp_path = md["cp_path"]
cp_work = join(cp_path,'work')

image_id = md["image_id"].strip()
harness_dir = os.path.dirname(join(cp_path, md["harnesses"][0]["source"]))

binary_path = join(md["binary_path"])




# Prepare work directory to make KLEE available inside the Docker container

sh_command = "tar -xvfj /app/orchestrator/klee/work.tar.gz ."
print(f"cd {cp_work}; {sh_command}")
sp.run(f"cd {cp_work}; {sh_command}", shell=True)

# Run KLEE

docker_command = f"""DOCKER_VOL_ARGS='{env_args}' ./run.sh custom run_bitcode.sh"""
print(f"cd {cp_path}; {docker_command}")
sp.run(f"cd {cp_path}; {docker_command}", shell=True)

