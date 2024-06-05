import os
import re
from os.path import join
from typing import Any
from typing import Dict
from typing import List

from app.core import definitions
from app.core import values
from app.core.task.stats.LocalizeToolStats import LocalizeToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.localize.AbstractLocalizeTool import AbstractLocalizeTool


class KernelSBFL(AbstractLocalizeTool):
    def __init__(self) -> None:
        self.bindings = {
            join(values.dir_main, "kernel_fuzz"): {"bind": "/tool", "mode": "rw"}
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
            join(values.dir_main, "kernel_fuzz") if self.locally_running else "/tool"
        )

        bug_info["cp_path"] = join(self.dir_expr, "src")
        bug_info["cp_src"] = join(self.dir_expr, "src", "src",bug_info['cp_sources'][0]['name'])
        bug_info["build_script"] = join(self.dir_setup, bug_info["build_script"])

        self.write_json(bug_info, join(self.dir_base_expr, "meta-data.json"))

        dir_failing_traces = join(self.dir_output, self.key_failing_test_identifiers)
        dir_passing_traces = join(self.dir_output, self.key_passing_test_identifiers)
        #self.run_command("mkdir -p {}".format(dir_failing_traces))
        #self.run_command("mkdir -p {}".format(dir_passing_traces))

        if (
            not bug_info[self.key_failing_test_identifiers]
            or not bug_info[self.key_passing_test_identifiers]
        ):
            self.error_exit("This tool requires positive and negative test cases")

        
        crashing_inputs = join(self.dir_expr,'src',bug_info["analysis_output"][0]["exploit_inputs"][0]["dir"])
        benign_inputs = join(self.dir_expr,'src',bug_info["analysis_output"][0]["benign_inputs"][0]["dir"])

        status = self.run_command(
            f"bash -c 'python3 {join(tool_folder,'crs_entrypoint.py')} {join(self.dir_base_expr,'meta-data.json')}  {crashing_inputs }:{dir_failing_traces}'",
            self.log_output_path,
            dir_path=tool_folder,
        )

        status = self.run_command(
            f"bash -c 'python3 {join(tool_folder,'crs_entrypoint.py')} {join(self.dir_base_expr,'meta-data.json')}  {benign_inputs}:{dir_passing_traces}'",
            self.log_output_path,
            dir_path=tool_folder,
        )

        cp_sources = list(map(lambda x: x["name"], bug_info["cp_sources"]))

        command = f"""python3 {join(tool_folder,'sbfl.py')} 
        {dir_failing_traces} 
        {dir_passing_traces} 
        -b {join(self.dir_expr,'src',bug_info[self.key_bin_path])}  
        -a {task_config_info.get(self.key_fl_formula,'ochiai').lower()} 
        -e { ','.join( cp_sources  ) }
        {task_config_info.get(self.key_tool_params, '')}
        """.replace(
            "\n", " "
        )

        if (
            definitions.KEY_TIEBREAKER_FUNCTIONS in bug_info
            and bug_info[definitions.KEY_TIEBREAKER_FUNCTIONS]
        ):
            tiebreaker_info = join(self.dir_output, "tiebreaker_function_list.json")
            self.write_json(
                bug_info[definitions.KEY_TIEBREAKER_FUNCTIONS], tiebreaker_info
            )
            command += f" --tiebreak-functions-path {tiebreaker_info}"

        if (
            definitions.KEY_TIEBREAKER_FILES in bug_info
            and bug_info[definitions.KEY_TIEBREAKER_FILES]
        ):
            tiebreaker_info = join(self.dir_output, "tiebreaker_file_list.json")
            self.write_json(bug_info[definitions.KEY_TIEBREAKER_FILES], tiebreaker_info)
            command += f" --tiebreak-files-path {tiebreaker_info}"

        status = self.run_command(command, log_file_path=self.log_output_path)

        # self.run_command("rm -rf {}".format(dir_failing_traces))
        # self.run_command("rm -rf {}".format(dir_passing_traces))

        self.process_status(status)

        self.timestamp_log_end()

        if self.is_file(join(self.dir_output, "ochiai.json")):
            localization_info = self.read_json(join(self.dir_output, "ochiai.json"))

            new_metadata = {
                "generator": "kernelsbfl",
                "confidence": 1,
                "localization": localization_info,
            }

            self.write_json(
                [{self.key_analysis_output: [new_metadata]}],
                join(self.dir_output, "meta-data.json"),
            )
        else:
            new_metadata = {
                "generator": "kernelsbfl",
                "confidence": 1,
                "localization": [],
            }

            self.write_json(
                [{self.key_analysis_output: [new_metadata]}],
                join(self.dir_output, "meta-data.json"),
            )

        self.emit_highlight("log file: {0}".format(self.log_output_path))

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

        output_file = join(self.dir_output, "ochiai.json")
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
            output_lines = self.read_json(output_file, encoding="iso-8859-1")
            if output_lines:
                fix_files = set()
                fix_locs = set()
                for _l in output_lines:
                    src_file = _l.get(self.key_fix_file)
                    fix_files.add(src_file)
                    for x in _l.get(self.key_fix_lines, []):
                        loc = f"{src_file}:{x}"
                        fix_locs.add(loc)
                self.stats.fix_loc_stats.fix_locs = len(fix_locs)
                self.stats.fix_loc_stats.source_files = len(fix_files)

        else:
            self.emit_error("no output file found")
            self.stats.error_stats.is_error = True

        if self.stats.error_stats.is_error:
            self.emit_error("[error] error detected in logs")
        if is_timeout:
            self.emit_warning("[warning] timeout before ending")
        return self.stats
