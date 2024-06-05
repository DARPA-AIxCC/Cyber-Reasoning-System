import os
import re
from datetime import datetime
from os.path import join
import time
from typing import Any
from typing import Dict
from typing import List

from app.core import values
from app.core import definitions
from app.core.task.stats.LocalizeToolStats import LocalizeToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.localize.AbstractLocalizeTool import AbstractLocalizeTool


class JaCoCo(AbstractLocalizeTool):
    def __init__(self) -> None:
        self.name = os.path.basename(__file__)[:-3].lower()
        self.bindings = {
            join(values.dir_main, "java-sbfl"): {"bind": "/tool", "mode": "rw"}
        }
        super().__init__(self.name)
        self.image_name = "ubuntu:22.04"

    def locate(self) -> None:
        pass

    def invoke(
        self, bug_info: Dict[str, Any], task_config_info: Dict[str, Any]
    ) -> None:

        timeout_h = str(task_config_info[self.key_timeout])

        self.timeout_h = timeout_h

        tool_folder = (
            join(values.dir_main, "java-sbfl") if self.locally_running else "/tool"
        )

        self.tool_folder = tool_folder

        # start running
        self.timestamp_log_start()

        if not self.is_file(join(self.dir_setup,'.build_default')):
            self.run_command(
                f"bash {join(self.dir_expr,'src',bug_info[self.key_build_script])}"
            )

        self.run_command(
            f"""timeout -k 5m {timeout_h}h 
            python3 {join(tool_folder,'java_sbfl.py')} 
            -c {join(self.dir_expr,'src')}
            --classpath { join(self.dir_expr,'src')+'/' +os.path.dirname(bug_info['harnesses'][0]['binary'])} 
            -b {join(self.dir_output,'backup')} 
            instrument""".replace(
                "\n", " "
            )
        )

        dir_failing_traces = join(self.dir_output, self.key_failing_test_identifiers)
        dir_passing_traces = join(self.dir_output, self.key_passing_test_identifiers)
        self.run_command("mkdir -p {}".format(dir_failing_traces))
        self.run_command("mkdir -p {}".format(dir_passing_traces))

        for i,failing_test_identifier in enumerate(bug_info[self.key_failing_test_identifiers]):
            if i > task_config_info.get(definitions.KEY_CONFIG_FAILING_TEST_COUNT,30):
                break
            
            self.run_trace(
                bug_info,
                dir_failing_traces,
                join(self.dir_expr, "src", "tests", failing_test_identifier),
            )

        for i,passing_test_identifier in enumerate(bug_info[self.key_passing_test_identifiers]):
            if i > task_config_info.get(definitions.KEY_CONFIG_PASSING_TEST_COUNT,30):
                break
            self.run_trace(
                bug_info,
                dir_passing_traces,
                join(self.dir_expr, "src", "tests", passing_test_identifier),
            )

        analysis_command = f"""timeout -k 5m {timeout_h}h python3 
        {join(tool_folder,'java_sbfl.py')} 
        -c {join(self.dir_expr,'src')} 
        --classpath { join(self.dir_expr,'src')+'/' +os.path.dirname(bug_info['harnesses'][0]['binary'])} 
        -b {join(self.dir_output,'backup')} 
        calculate 
        -p {dir_passing_traces} 
        -f {dir_failing_traces} 
        { ' ' if definitions.KEY_TIEBREAKER_FILES not in bug_info else '-tbfi ' + ' -tbfi '.join(bug_info[definitions.KEY_TIEBREAKER_FILES])  }
        -o {join(self.dir_output,'ochiai.json')} 
        --formula=ochiai""".replace(
            "\n", " "
        )

        status = self.run_command(analysis_command, self.log_output_path, tool_folder)

        self.process_status(status)

        if self.is_file(join(self.dir_output, "ochiai.json")):
            localization_info = self.read_json(join(self.dir_output, "ochiai.json"))
            updated_localization_info = []
            for _l in localization_info:
                src_file = _l.get(self.key_fix_file)
                rel_src_file = src_file.replace(join(self.dir_expr, "src"), "")
                
                if bug_info["selected_source"] not in rel_src_file:
                    continue
                
                rel_src_file = rel_src_file[rel_src_file.index(bug_info["selected_source"])+len(bug_info["selected_source"])+1:]
                
                _l[self.key_fix_file] = rel_src_file
                updated_localization_info.append(_l)
            new_metadata = {
                "generator": "jacocosbfl",
                "confidence": 1,
                "localization": updated_localization_info,
            }

            self.write_json(
                [{self.key_analysis_output: [new_metadata]}],
                join(self.dir_output, "meta-data.json"),
            )

        self.timestamp_log_end()
        self.emit_highlight("\t\t\tlog file: {0}".format(self.log_output_path))

    def run_trace(self, bug_info, target_dir, test_identifier):
        self.run_command(
            "bash {} {} {}".format(
                join(self.dir_expr, "src", "trace.sh"), test_identifier, target_dir
            ),
            dir_path=join(self.dir_expr, "src"),
        )
        self.run_command(
            f"""timeout -k 5m {self.timeout_h}h python3 {join(self.tool_folder,'java_sbfl.py')} 
            -c {join(self.dir_expr,'src')} 
            --classpath { join(self.dir_expr,'src')+'/' +os.path.dirname(bug_info['harnesses'][0]['binary'])} 
            -b {join(self.dir_output,'backup')} 
            export -o {join(target_dir, str(int(time.time())) + '.trace')}""".replace(
                "\n", " "
            )
        )

    def save_artifacts(self, dir_info: Dict[str, str]) -> None:
        """
        Save useful artifacts from the repair execution
        output folder -> self.dir_output
        logs folder -> self.dir_logs
        The parent method should be invoked at last to archive the results
        """
        super(JaCoCo, self).save_artifacts(dir_info)

    def analyse_output(
        self, dir_info: DirectoryInfo, bug_id: str, fail_list: List[str]
    ) -> LocalizeToolStats:
        self.emit_normal("reading output")
        if not self.log_output_path or not self.is_file(self.log_output_path):
            self.emit_warning("no output log file found")
            return self.stats

        self.emit_highlight(" Log File: " + self.log_output_path)
        if self.is_file(self.log_output_path):
            log_lines = self.read_file(self.log_output_path, encoding="iso-8859-1")
            for line in log_lines:
                if "Runtime Error" in line:
                    self.stats.error_stats.is_error = True
        localization_file = join(self.dir_output, "ochiai.json")
        if self.is_file(localization_file):
            result_list = self.read_json(localization_file)
            if len(result_list) == 0:
                self.emit_error("no localized locations found")
                self.stats.error_stats.is_error = True
            fix_files = set()
            fix_lines = list()
            for _l in result_list:
                fix_files.add(_l.get(self.key_fix_file))
                fix_lines += _l.get(self.key_fix_lines, [])
            self.stats.fix_loc_stats.fix_locs = len(fix_lines)
            self.stats.fix_loc_stats.source_files = len(fix_files)
        else:
            self.emit_error("no localization file found")
            self.stats.error_stats.is_error = True

        if self.stats.error_stats.is_error:
            self.emit_error("[error] error detected in logs")
        return self.stats
