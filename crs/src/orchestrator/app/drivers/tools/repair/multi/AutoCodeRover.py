import json
import os
from os.path import join
from random import randint
from typing import Any
from typing import Dict
from typing import List

from app.core import values
from app.core.task.stats.RepairToolStats import RepairToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.repair.AbstractRepairTool import AbstractRepairTool


class AutoCodeRover(AbstractRepairTool):
    def __init__(self) -> None:
        self.name = os.path.basename(__file__)[:-3].lower()
        self.bindings = {join(values.dir_main, "acr"): {"bind": "/tool", "mode": "rw"}}
        super().__init__(self.name)
        # preferably change to a container with the dependencies to reduce setup time
        self.image_name = "rshariffdeen/acr"

    def locate(self) -> None:
        pass

    def prepare_scripts(self, bug_info: Dict[str, Any]) -> None:
        self.emit_normal("generating wrapper scripts")
        _test_path = join(self.dir_setup, self.name, "test.sh")
        _trace_path = join(self.dir_setup, self.name, "trace.sh")
        _reset_path = join(self.dir_setup, self.name, "reset.sh")
        _validate_path = join(self.dir_setup, self.name, "validate.sh")
        _instrument_path = join(self.dir_setup, self.name, "instrument.sh")
        dir_src = join(self.dir_expr, "src")
        binary_abs_path = join(dir_src, bug_info[self.key_bin_path])
        mkdir_cmd = f"mkdir -p {join(self.dir_setup, self.name,'trace_instrumentation', 'hooks')}"
        self.run_command(mkdir_cmd)
        copy_cmd = f"cp /opt/auto-code-rover/scripts/tracing/instrument.py {self.dir_setup}/{self.name}/trace_instrumentation"
        self.run_command(copy_cmd)
        copy_cmd = f"cp /opt/auto-code-rover/scripts/tracing/src_tracer.c {self.dir_setup}/{self.name}/trace_instrumentation/hooks"
        self.run_command(copy_cmd)

        self.write_file(
            [
                "#!/bin/bash\n",
                f"TRACE_FILE=$2/trace_$(date +%s) {binary_abs_path} $1 out.tif ; echo done\n",
            ],
            _trace_path,
        )
        self.write_file(["#!/bin/bash\n", f"exit 0\n"], _validate_path)
        self.write_file(
            [
                "#!/bin/bash\n",
                f"cd {dir_src}\n",
                f"git checkout . 2>&1 >/dev/null\n",
                f"bash {self.dir_setup}/clean.sh 2>&1 >/dev/null\n",
                f"./autogen.sh 2>&1 >/dev/null\n",
                f"bash {self.dir_setup}/config.sh 2>&1 >/dev/null\n",
                f"bash {self.dir_setup}/build.sh 2>&1 >/dev/null\n",
            ],
            _reset_path,
        )
        self.write_file(
            [
                "#!/bin/bash\n",
                f"cd {self.dir_setup}\n",
                f"bash test.sh $(basename $1)\n",
            ],
            _test_path,
        )

        self.write_file(
            [
                "#!/bin/bash\n",
                f"cd {join(self.dir_setup, self.name, 'trace_instrumentation', 'hooks')}\n",
                f"CC=gcc CXX=g++ e9compile src_tracer.c 2>&1 >/dev/null\n",
                f"cp src_tracer {join(self.dir_setup, self.name, 'trace_instrumentation')}\n",
                f"cd {join(self.dir_setup, self.name, 'trace_instrumentation')}\n",
                f"python3 instrument.py {binary_abs_path} 2>&1 >/dev/null\n",
                f"cp {binary_abs_path}*.tracer {binary_abs_path}\n",
            ],
            _instrument_path,
        )
        permission_cmd = (
            f"chmod +x {_test_path} {_instrument_path} {_trace_path} {_reset_path}"
        )
        self.run_command(permission_cmd)

    def prepare_metadata(
        self, bug_info: Dict[str, Any], metadata_path: str, script_path: str
    ) -> None:
        cp_sources = list(map(lambda x: x["name"], bug_info["cp_sources"]))
        harness_sources = list(
            map(lambda x: os.path.dirname(x["source"]), bug_info["harnesses"])
        )

        metadata = {
            "dirs": {
                "srcBenignTestDir": [
                    join(
                        self.dir_setup,
                        bug_info[self.key_analysis_output][0]["benign_inputs"][0][
                            "dir"
                        ],
                    )
                ],
                "srcCrashTestDir": [
                    join(
                        self.dir_setup,
                        bug_info[self.key_analysis_output][0]["exploit_inputs"][0][
                            "dir"
                        ],
                    )
                ],
                "sourcePath": [join(self.dir_expr, "src")],
                "traces": [join(self.dir_output, "traces")],
                "executable": [
                    join(self.dir_expr, "src", bug_info.get(self.key_bin_path, ""))
                ],
                "binJavaDir": [],
                "binTestDir": [],
                "srcJavaDir": [],
                "srcTestDir": [],
                "classpath": [],
            },
            "commands": {
                "instrument": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'instrument.sh')}'",
                "validate": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'build.sh')} && {join(script_path,'validate.sh')}'",
                "run_test": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'test.sh')} @POV@'",
                "get_trace": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'trace.sh')} @POV@ @TARGET_DIR@'",
                "reset": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'reset.sh')}'",
                "reproduce": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'build.sh')} && {join(script_path,'validate.sh')}'",
                "setup": f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path,'setup.sh')}'",
            },
            "localization": bug_info.get(self.key_localization, []),
            "cp_sources": cp_sources,
        }
        if bug_info[self.key_benchmark] == "vulnloc":
            metadata["commands"][
                "validate"
            ] = f"bash -c 'EXPERIMENT_DIR={self.dir_base_expr} {join(script_path, 'validate.sh')}'"

        self.write_json(metadata, metadata_path)

    def instrument(self, bug_info: Dict[str, Any]) -> None:
        metadata_path = join(self.dir_output, "acr_metadata.json")
        benchmark_name = bug_info[self.key_benchmark]
        self.run_command(f"mkdir {join(self.dir_output, 'traces')}")
        if str(benchmark_name).lower() == "vulnloc":
            self.emit_debug("Preparing scripts")
            self.prepare_scripts(bug_info)
            self.prepare_metadata(
                bug_info, metadata_path, join(self.dir_setup, self.name)
            )
        else:
            self.prepare_metadata(bug_info, metadata_path, self.dir_setup)
        self.metadata_path = metadata_path

    def create_meta_data(self) -> None:
        dir_patches = f"{self.dir_output}/patches"
        patch_file_list = self.list_dir(dir_patches)
        patch_list = []
        for _f in patch_file_list:
            _content = self.read_file(_f, encoding="iso-8859-1")
            _filtered_content = [l.strip() for l in _content[2:]]
            _p = {
                "source_path": "",
                "line_number": "",
                "describer_id": "",
                "description": "",
                "fixer_id": "",
                "reviewer_id": "",
                "generator": self.name,
                "patch_file": str(_f).split("/")[-1],
                "patch_content": _filtered_content,
            }
            patch_list.append(_p)

        metadata = {
            "patches_dir": join(self.dir_output, "patches"),
            "patches": patch_list,
        }
        self.write_json(
            metadata,
            join(self.dir_output, "meta-data.json"),
        )

    def invoke(
        self, bug_info: Dict[str, Any], task_config_info: Dict[str, Any]
    ) -> None:
        """
        self.dir_logs - directory to store logs
        self.dir_setup - directory to access setup scripts
        self.dir_expr - directory for experiment
        self.dir_output - directory to store artifacts/output
        """

        timeout_h = str(task_config_info[self.key_timeout])
        timeout_m = str(float(timeout_h) * 60)

        tool_folder = (
            join(values.dir_main, "acr")
            if self.locally_running
            else "/opt/auto-code-rover"
        )
        if self.key_language not in bug_info:
            self.emit_error("Need to know language for the subject")
        language = bug_info[self.key_language]
        metadata_path = self.metadata_path

        if self.key_bug_reports not in bug_info:
            self.error_exit("Need bug report for the subject")
        commit_id = bug_info.get(self.key_commit_checkout, "HEAD")

        repair_command = f"""timeout -k 5m {timeout_h}h python3 app/main.py scripted-{language}
        --task-id {bug_info[self.key_bug_id]}
        --path {join(self.dir_expr,'src','src',bug_info['selected_source'])}
        --commit {commit_id}
        --bug-report-path {join(self.dir_setup,bug_info[self.key_bug_reports][0])}
        --metadata-file {metadata_path}
        --output-dir {join(self.dir_output)}
        { ('--bug-intro-commit ' + bug_info['commit']) if 'commit' in bug_info else ''  } 
        --model litellm-gpt-4o-2024-05-13
        --model-temperature 0.0
        { '--enable-sbfl' if bug_info.get(self.key_localization, []) else ' '}
        """.replace(
            "\n", " "
        )

        # generate patches
        self.timestamp_log_start()
        openai_token = self.api_keys.get(self.key_openai_token, None)
        anthropic_token = self.api_keys.get(self.key_anthropic_token, None)
        google_field_name = ""
        if (
            self.key_gemini_token in self.api_keys
            and self.api_keys[self.key_gemini_token]
        ):
            if isinstance(self.api_keys[self.key_gemini_token], dict):
                self.emit_debug("Using dict")
                with open(join(self.dir_expr, "google_token.json"), "w") as f:
                    f.write(json.dumps(self.api_keys.get(self.key_gemini_token, "")))
                google_token = join(self.dir_expr, "google_token.json")
                google_field_name = "GOOGLE_APPLICATION_CREDENTIALS"
            elif isinstance(self.api_keys[self.key_gemini_token], str):
                self.emit_debug("Using str")
                google_token = self.api_keys[self.key_gemini_token]
                google_field_name = "GEMINI_API_KEY"

        status = self.run_command(
            repair_command,
            self.log_output_path,
            dir_path=tool_folder,
            env={
                "PYTHONPATH": tool_folder,
                "OPENAI_KEY": openai_token,
                "ANTHROPIC_API_KEY": anthropic_token,
                google_field_name: google_token,
            },
        )

        self.run_command(f"mkdir patches", dir_path=self.dir_output)
        list_output_dir = self.list_dir(self.dir_output, "*.diff")
        start = randint(1, 10000)
        if self.locally_running:
            list_output_dir.sort(key= lambda x: os.path.getmtime(x) )
        for _f in list_output_dir:
            self.run_command(
                f"cp {_f} {self.dir_output}/patches/{start}_{os.path.basename(_f)}",
                dir_path=self.dir_output,
            )
            start += 1

        self.create_meta_data()
        self.process_status(status)
        self.timestamp_log_end()
        self.emit_highlight("log file: {0}".format(self.log_output_path))

    def save_artifacts(self, dir_info: Dict[str, str]) -> None:
        """
        Save useful artifacts from the repair execution
        output folder -> self.dir_output
        logs folder -> self.dir_logs
        The parent method should be invoked at last to archive the results
        """
        super(AutoCodeRover, self).save_artifacts(dir_info)

    def analyse_output(
        self, dir_info: DirectoryInfo, bug_id: str, fail_list: List[str]
    ) -> RepairToolStats:
        """
        analyse tool output and collect information
        output of the tool is logged at self.log_output_path
        information required to be extracted are:

            self.stats.patches_stats.non_compilable
            self.stats.patches_stats.plausible
            self.stats.patches_stats.size
            self.stats.patches_stats.enumerations
            self.stats.patches_stats.generated

            self.stats.time_stats.total_validation
            self.stats.time_stats.total_build
            self.stats.time_stats.timestamp_compilation
            self.stats.time_stats.timestamp_validation
            self.stats.time_stats.timestamp_plausible
        """
        self.emit_normal("reading output")
        task_conf_id = str(self.current_task_profile_id.get("NA"))
        self.log_stats_path = join(
            self.dir_logs,
            "{}-{}-{}-stats.log".format(task_conf_id, self.name.lower(), bug_id),
        )

        if not self.log_output_path or not self.is_file(self.log_output_path):
            self.emit_warning("no output log file found")
            return self.stats

        self.emit_highlight("log File: " + self.log_output_path)

        if self.stats.error_stats.is_error:
            self.emit_error("error detected in logs")

        self.stats.patch_stats.plausible = 0
        self.stats.patch_stats.non_compilable = 0
        self.stats.patch_stats.size = 0
        self.stats.patch_stats.enumerations = 0

        if self.is_file(self.log_output_path):
            log_lines = self.read_file(self.log_output_path, encoding="iso-8859-1")

            for line in log_lines:
                if "Patch Generation (try" in line:
                    self.stats.patch_stats.enumerations += 1

        self.stats.patch_stats.size = self.stats.patch_stats.enumerations
        # count number of patch files
        self.dir_patch = join(self.dir_output, "patches")
        list_output_dir = self.list_dir(self.dir_patch)
        self.stats.patch_stats.generated = len(
            [name for name in list_output_dir if ".diff" in name]
        )
        return self.stats
