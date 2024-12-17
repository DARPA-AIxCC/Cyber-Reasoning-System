import os
import re
from os.path import join
from typing import Any, Tuple
from typing import Dict
from typing import List
import traceback
from app.core import definitions
from app.core import values
from app.core.task.stats.LocalizeToolStats import LocalizeToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.localize.AbstractLocalizeTool import AbstractLocalizeTool


class E9PatchNeoSBFL(AbstractLocalizeTool):
    def __init__(self) -> None:
        self.bindings = {
            join(values.dir_main, "sbfl_neo_local"): {
                "bind": "/sbfl_local",
                "mode": "rw",
            }
        }
        self.name = os.path.basename(__file__)[:-3].lower()
        super().__init__(self.name)

    def locate(self) -> None:
        pass

    def invoke(
        self, bug_info: Dict[str, Any], task_config_info: Dict[str, Any]
    ) -> None:

        task_conf_id = str(self.current_task_profile_id.get("NA"))
        bug_id = str(bug_info[self.key_bug_id])
        timeout = str(task_config_info[self.key_timeout])
        self.log_output_path = join(
            self.dir_logs,
            "{}-{}-{}-output.log".format(task_conf_id, self.name.lower(), bug_id),
        )

        timeout_m = str(float(timeout) * 60)
        additional_tool_param = task_config_info[self.key_tool_params]

        if self.key_bin_path not in bug_info:
            self.emit_error("No binary path found")

        self.timestamp_log_start()

        tool_folder = (
            "/sbfl"
            if not self.locally_running
            else join(values.dir_main, "sbfl_neo_local")
        )

        self.emit_normal("Instrumenting binary")

        if os.path.exists(join(self.dir_expr, "src", "instrument.sh")):
            self.run_command("bash instrument.sh", dir_path=join(self.dir_expr, "src"))

        for artifact_info in bug_info["cp_sources"]:
            for artifact in artifact_info.get("artifacts", []):
                status, output = self.exec_command(
                    f"file {join(self.dir_expr,'src',artifact)}"
                )

                if status == 0:
                    if output:
                        (out, err) = output
                        if "elf" not in out.decode().lower():
                            continue
                    self.run_command(
                        f"{tool_folder}/sbfl-tool replace {join(self.dir_expr,'src',artifact)}",
                        dir_path=tool_folder,
                    )

        self.run_command(
            f"{tool_folder}/sbfl-tool replace {join(self.dir_expr,'src',bug_info['harnesses'][0]['binary'])}",
            dir_path=tool_folder,
        )

        dir_failing_traces = join(self.dir_output, self.key_failing_test_identifiers)
        dir_passing_traces = join(self.dir_output, self.key_passing_test_identifiers)
        self.run_command("mkdir -p {}".format(dir_failing_traces))
        self.run_command("mkdir -p {}".format(dir_passing_traces))

        if (
            not bug_info[self.key_failing_test_identifiers]
            or not bug_info[self.key_passing_test_identifiers]
        ):
            self.error_exit("This tool requires positive and negative test cases")

        has_trace = self.is_file(join(self.dir_expr, "src", "trace.sh"))

        for failing_test_identifier in bug_info[self.key_failing_test_identifiers]:
            if has_trace:
                self.run_trace(
                    bug_info,
                    dir_failing_traces,
                    join(self.dir_expr, "src", "tests", failing_test_identifier),
                )
            else:
                self.run_test(bug_info, dir_failing_traces, failing_test_identifier)

        for passing_test_identifier in bug_info[self.key_passing_test_identifiers]:
            if has_trace:
                self.run_trace(
                    bug_info,
                    dir_passing_traces,
                    join(self.dir_expr, "src", "tests", passing_test_identifier),
                )
            else:
                self.run_test(bug_info, dir_passing_traces, passing_test_identifier)

        cp_sources = list(map(lambda x: x["name"], bug_info["cp_sources"]))
        harness_sources = list(
            map(lambda x: os.path.dirname(x["source"]), bug_info["harnesses"])
        )

        if self.is_file(join(self.dir_expr, "src", "out", "SBFL.prof")):
            status = 0
            try:
                localization_info = self.process_localization_file(bug_info)
            except Exception as e:
                self.emit_warning(e)
                traceback.print_exc()
                status = 1
                localization_info = []
                pass
            new_metadata = {
                "generator": "e9patchneosbfl",
                "confidence": 1,
                "localization": localization_info,
            }

            self.write_json(
                [{self.key_analysis_output: [new_metadata]}],
                join(self.dir_output, "meta-data.json"),
            )
        else:
            status = 1
            new_metadata = {
                "generator": "e9patchneosbfl",
                "confidence": 1,
                "localization": [],
            }

            self.write_json(
                [{self.key_analysis_output: [new_metadata]}],
                join(self.dir_output, "meta-data.json"),
            )

        # self.run_command("rm -rf {}".format(dir_failing_traces))
        # self.run_command("rm -rf {}".format(dir_passing_traces))

        self.process_status(status)

        self.timestamp_log_end()

        self.emit_highlight("log file: {0}".format(self.log_output_path))

    def process_localization_file(self, bug_info: Dict[str, Any]):

        lines = self.read_file(join(self.dir_expr, "src", "out", "SBFL.prof"))

        ungrouped_lines: Dict[Tuple[str, str, str], List[int]] = {}

        for trace_line in lines[3:]:
            src, PX, PN, FX, FN, score, *func = trace_line.split(" ")

            if len(func) != 0:
                func = func[0]
            else:
                func = ""

            for source in bug_info["cp_sources"]:
                file, line, rest = src.split(":")

                if "/src/llvm-project" in file:
                    continue

                prefix_search = re.match("/src/harnesses/(.+?)/", file)
                cp_source_names = map(
                    lambda x: x["name"], bug_info.get("cp_sources", [])
                )

                if prefix_search:
                    if not prefix_search.group(1) in cp_source_names:
                        file = file[len(prefix_search.group(0)) :]
                    else:
                        file = file.removeprefix("/src/harnesses/")

                if source["name"] in file and source["name"] in os.path.dirname(file):
                    file = file[file.index(source["name"]) + len(source["name"]) + 1 :]
                    
                if (file, score, func) not in ungrouped_lines:
                    ungrouped_lines[(file, score, func)] = []
                ungrouped_lines[(file, score, func)].append(int(line))
                break

        localization_info = []
        for (file, score, func), lines in ungrouped_lines.items():
            localization_info.append(
                {
                    "source_file": file,
                    "line_numbers": lines,
                    "score": float(score.split("=")[1]),
                    "function": func,
                }
            )
        try:
            if definitions.KEY_TIEBREAKER_FILES in bug_info:
                for depth, tiebreaker_file in enumerate(
                    bug_info[definitions.KEY_TIEBREAKER_FILES]
                ):
                    name = tiebreaker_file.split(":")[0]
                    for entry in localization_info:
                        if name in entry["source_file"]:
                            entry["score"] += 0.0001 - depth * 0.000005
        except Exception as e:
            pass

        localization_info.sort(key=lambda x: x["score"], reverse=True)
        return localization_info[:20]

    def run_test(self, bug_info, target_dir, test_identifier):
        self.run_command(
            "bash {} {}".format(bug_info[self.key_test_script], test_identifier),
            dir_path=join(self.dir_expr, "src"),
            env={
                "TRACE_FILE": join(
                    target_dir, os.path.basename(test_identifier) + ".trace"
                )
            },
        )

    def run_trace(self, bug_info, target_dir, test_identifier):
        self.run_command(
            "bash {} {} {}".format(
                join(self.dir_expr, "src", "trace.sh"), test_identifier, target_dir
            ),
            dir_path=join(self.dir_expr, "src"),
        )

    def analyse_output(
        self, dir_info: DirectoryInfo, bug_id: str, fail_list: List[str]
    ) -> LocalizeToolStats:
        self.emit_normal("reading output")
        if not self.log_output_path or not self.is_file(self.log_output_path):
            self.emit_warning("no output log file found")
            return self.stats

        output_file = join(self.dir_expr, "src", "out", "SBFL.prof")
        self.emit_highlight(" Log File: " + self.log_output_path)
        is_timeout = True
        if self.is_file(self.log_output_path):
            log_lines = self.read_file(self.log_output_path, encoding="iso-8859-1")
            for line in log_lines:
                if "Runtime Error" in line:
                    self.stats.error_stats.is_error = True
                elif "statistics" in line:
                    is_timeout = False
        if self.is_file(output_file):
            output_lines = self.read_file(output_file, encoding="iso-8859-1")
            # if output_lines:
            #     fix_files = set()
            #     fix_locs = set()
            #     for _l in output_lines:
            #         src_file = _l.get(self.key_fix_file)
            #         fix_files.add(src_file)
            #         for x in _l.get(self.key_fix_lines, []):
            #             loc = f"{src_file}:{x}"
            #             fix_locs.add(loc)
            #     self.stats.fix_loc_stats.fix_locs = len(fix_locs)
            #     self.stats.fix_loc_stats.source_files = len(fix_files)

        else:
            self.emit_error("no output file found")
            self.stats.error_stats.is_error = True

        if self.stats.error_stats.is_error:
            self.emit_error("[error] error detected in logs")
        if is_timeout:
            self.emit_warning("[warning] timeout before ending")
        return self.stats
