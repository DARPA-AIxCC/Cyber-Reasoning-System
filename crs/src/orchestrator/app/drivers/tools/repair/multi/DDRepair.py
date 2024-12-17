import json
import os
from os.path import join
from typing import Any
from typing import Dict
from typing import List

from app.core import values
from app.core.task.stats.RepairToolStats import RepairToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.repair.AbstractRepairTool import AbstractRepairTool


class DDRepair(AbstractRepairTool):
    def __init__(self) -> None:
        self.name = os.path.basename(__file__)[:-3].lower()
        self.bindings = {
            join(values.dir_main, "dd_repair"): {"bind": "/tool", "mode": "rw"}
        }
        super().__init__(self.name)
        # preferably change to a container with the dependencies to reduce setup time

    def locate(self) -> None:
        pass

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
            join(values.dir_main, "dd_repair") if self.locally_running else "/tool"
        )

        self.run_command(f"mkdir -p {join(self.dir_output,'patches')}")

        bug_info["cp_path"] = join(self.dir_expr, "src")
        bug_info["cp_src"] = join(
            self.dir_expr,
            "src",
            "src",
            bug_info.get("selected_source", bug_info["cp_sources"][0]["name"]),
        )
        bug_info["build_script"] = join(self.dir_setup, bug_info["build_script"])
        bug_info["validate_script"] = join(self.dir_setup, bug_info["validate_script"])

        self.write_json(bug_info, join(self.dir_base_expr, "meta-data.json"))

        repair_command = f"timeout -k 5m {timeout_h}h python3 {tool_folder}/dd-repair.py {join(self.dir_base_expr,'meta-data.json')} -o {join(self.dir_output,'patches','out.diff')}"

        # generate patches
        self.timestamp_log_start()

        status = self.run_command(
            repair_command,
            self.log_output_path,
            dir_path=join(self.dir_expr, "src"),
        )

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
        super(DDRepair, self).save_artifacts(dir_info)

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
