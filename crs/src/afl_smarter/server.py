#!/bin/python3

from flask import Flask, request, jsonify
import subprocess as sp
import os
import tempfile
import uuid
from os.path import join

app = Flask(__name__)
injection = '<Agent name="LinAgent"><Monitor class="LinuxDebugger"><Param name="Executable" value="NotSpecified"/><Param name="GdbPath"  value="/home/ubuntu/test_monitor"/><Param name="RestartOnEachTest"  value="true"/><Param name="CpuKill" value="true"/></Monitor></Agent>'


@app.get("/health")
def health_check():
    return "", 200


@app.post("/start-g4")
def start_g4_job():
    meta_data = request.get_json(silent=True)
    out_g4 = f"gram_{meta_data['subject']}_{meta_data['bug_id']}"
    sp.run(
        [
            "python3",
            "gen_g4/generate_g4.py",
            join(meta_data["cp_path"], meta_data["harnesses"][0]["source"]),
            out_g4,
            meta_data.get("name", meta_data["subject"]),
        ],
        env={**os.environ, "OPENAI_API_KEY": meta_data["open_ai"]},
    )

    os.environ["OPENAI_API_KEY"] = meta_data["open_ai"]
    tmp_dir = tempfile.TemporaryDirectory(suffix="_tmp")
    tmp_index = tempfile.NamedTemporaryFile("r", -1, suffix="_index")
    out_dir = join(
        os.getenv("AIXCC_CRS_SCRATCH_SPACE", "/tmp"),
        "peach",
        meta_data["subject"],
        meta_data["bug_id"],
    )
    os.makedirs(out_dir, exist_ok=True)
    grammarinator_env = {
        "AIxCC_BATCH_SIZE": str(50),
        "AIxCC_INDEX_FILE": tmp_index.name,
        "AIxCC_TMP_DIR": tmp_dir.name,
        "AIxCC_OUT_DIR": out_dir,
        "AIxCC_MAX_COUNT": str(100000),
        "AIxCC_MAX_DEPTH": str(50),
    }

    sp.Popen(
        [
            "/home/ubuntu/cfg_fuzzing",
            *list(
                map(
                    lambda x: x,
                    filter(lambda t: t.endswith(".g4"), os.listdir(out_g4)),
                )
            ),
        ],
        cwd=out_g4,
        env={**os.environ, **grammarinator_env},
    )
    return str(uuid.uuid1()),200


@app.post("/start-peach")
def start_peach_job():
    meta_data = request.get_json(silent=True)

    os.environ["OPENAI_API_KEY"] = meta_data["open_ai"]
    out_pit = f"pit_{meta_data['subject']}_{meta_data['bug_id']}.xml"

    sp.run(
        [
            "python3",
            "gen_pit/generate_pit.py",
            join(meta_data["cp_path"], meta_data["harnesses"][0]["source"]),
            out_pit,
            meta_data.get("name", meta_data["subject"]),
        ],
        env={**os.environ, "OPENAI_API_KEY": meta_data["open_ai"]},
    )

    tmp_index = tempfile.NamedTemporaryFile("r", -1, suffix="_9index")
    tmp_dir = tempfile.TemporaryDirectory(suffix="_tmp")

    out_dir = join(
        os.getenv("AIXCC_CRS_SCRATCH_SPACE", "/tmp"),
        "peach",
        meta_data["subject"],
        meta_data["bug_id"],
    )

    os.makedirs(out_dir, exist_ok=True)

    peach_env = {
        "AIxCC_BATCH_SIZE": str(200),
        "AIxCC_INDEX_FILE": tmp_index.name,
        "AIxCC_TMP_DIR": tmp_dir.name,
        "AIxCC_OUT_DIR": out_dir,
    }

    os.system(f"sed -i 's|</StateModel>|</StateModel>{injection}|' {out_pit}")
    os.system(f"sed -i -E 's|<Data\\s*fileName=\"/dev/null\"\\s*/>||g' {out_pit}")
    os.system(f"sed -i -E 's|</Test>|<Agent ref=\"LinAgent\" platform=\"linux\"/></Test>|g' {out_pit}")
    os.system(f"sed -i -E 's|<Param\\s*name=\"FileName\"\\s*value=\".*?\"\\s*/>|<Param name=\"FileName\" value=\"fuzz.bin\"/>|g' {out_pit}")
    

    sp.Popen(
        [
            "/home/ubuntu/peach-3.0.202-source/output/linux_x86_64_release/bin/peach",
            "--range",
            "1,2500000",
            out_pit,
        ],
        env={**os.environ, **peach_env},
    )
    return str(uuid.uuid1()), 200


@app.post("/stop")
def stop_job():
    return "", 200
