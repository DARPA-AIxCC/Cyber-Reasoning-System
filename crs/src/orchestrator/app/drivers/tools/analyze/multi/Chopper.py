import os
from os.path import join
from typing import Any
from typing import Dict
from typing import List

from app.core import values
from app.core.task.stats.AnalysisToolStats import AnalysisToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.analyze.AbstractAnalyzeTool import AbstractAnalyzeTool


class Chopper(AbstractAnalyzeTool):
    def __init__(self) -> None:
        self.name = os.path.basename(__file__)[:-3].lower()
        self.bindings = {
            join(values.dir_main, "chopper"): {"bind": "/tool", "mode": "rw"}
        }
        super().__init__(self.name)
        # preferably change to a container with the dependencies to reduce setup time
        self.image_name = "ubuntu:22.04"
        self.commit_path = None

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

        tool_folder = (
            join(values.dir_main, "chopper") if self.locally_running else "/tool"
        )

        bug_info["cp_path"] = join(self.dir_expr, "src")
        bug_info["build_script"] = join(self.dir_setup, bug_info["build_script"])
        bug_info["test_script"] = join(self.dir_setup, bug_info["test_script"])

        metadata_path = join(self.dir_base_expr, "meta-data.json")
        self.write_json(bug_info, metadata_path)

        # generate patches
        self.timestamp_log_start()

        self.commit_path = join(self.dir_output, "commit.txt")
        self.run_command(f"mkdir -p {self.dir_output}")

        script_path = join(tool_folder, "main.py")
        status = self.run_command(
            f"python3 {script_path} {metadata_path} {self.commit_path} ",
            self.log_output_path,
        )

        if self.is_file(self.commit_path):
            commit_info = self.read_file(self.commit_path)

            self.write_json(
                [
                    {
                        "commit": commit_info[0].strip(),
                        "selected_source": commit_info[1].strip(),
                    }
                ],
                join(self.dir_output, "meta-data.json"),
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
        super(Chopper, self).save_artifacts(dir_info)

    def analyse_output(
        self, dir_info: DirectoryInfo, bug_id: str, fail_list: List[str]
    ) -> AnalysisToolStats:
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
        self.stats.report_stats.generated = 0
        if self.commit_path and self.is_file(self.commit_path):
            content = self.read_file(self.commit_path)
            if len(content) > 0:
                self.stats.report_stats.generated = 1

        return self.stats
