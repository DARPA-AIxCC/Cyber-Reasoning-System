import os
from os.path import join
from typing import Any
from typing import Dict
from typing import List

from app.core import values
from app.core.task.stats.FuzzToolStats import FuzzToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.fuzz.AbstractFuzzTool import AbstractFuzzTool


class KLEE(AbstractFuzzTool):
    def __init__(self) -> None:
        self.name = os.path.basename(__file__)[:-3].lower()
        self.bindings = {
            join(values.dir_main, "klee"): {"bind": "/tool", "mode": "rw"}
        }
        super().__init__(self.name)
        # preferably change to a container with the dependencies to reduce setup time
        self.image_name = "ubuntu:22.04"
        self.extends_subject = False

    def locate(self) -> None:
        pass

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

        self.emit_debug(bug_info)

        tool_folder = (
            join(values.dir_main, "klee") if self.locally_running else "/tool"
        )

        # generate patches
        self.timestamp_log_start()

        bug_info["cp_path"] = join(self.dir_expr, "src")
        bug_info["build_script"] = join(self.dir_setup, bug_info["build_script"])

        self.write_json(bug_info, join(self.dir_base_expr, "meta-data.json"))

        status = self.run_command(
            f"bash -c 'python3 {join(tool_folder,'klee-runner.py')} {join(self.dir_base_expr,'meta-data.json')}'",
            self.log_output_path,
            dir_path=tool_folder,
        )

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
        super(KLEE, self).save_artifacts(dir_info)

    def analyse_output(
        self, dir_info: DirectoryInfo, bug_id: str, fail_list: List[str]
    ) -> FuzzToolStats:
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

        return self.stats
