import os
import re
from datetime import datetime
from os.path import join
from typing import Any
from typing import Dict
from typing import List

from app.core import values
from app.core.task.stats.AnalysisToolStats import AnalysisToolStats
from app.core.task.typing.DirectoryInfo import DirectoryInfo
from app.drivers.tools.analyze.AbstractAnalyzeTool import AbstractAnalyzeTool


class LLMSymbolic(AbstractAnalyzeTool):
    def __init__(self) -> None:
        self.name = os.path.basename(__file__)[:-3].lower()
        self.bindings = {
            join(values.dir_main, "llm_symbolic"): {"bind": "/tool", "mode": "rw"}
        }
        super().__init__(self.name)
        self.image_name = "ubuntu:22.04"

    def locate(self) -> None:
        pass

    def invoke(
        self, bug_info: Dict[str, Any], task_config_info: Dict[str, Any]
    ) -> None:

        san_mapper = {
            "File read/write hook path": "FileSystemTraversal",
            "LDAP Injection": "LdapInjection",
            "OS Command Injection": "OsCommandInjection",
            "Remote Code Execution": "ReflectiveCall,Deserializaton,ExpressionLanguageInjection",
            "Integer Overflow": "IntegerOverflow",
            "File read/write": "FileReadWrite",
            "Server Side Request Forgery (SSRF)": "ServerSideRequestForgery",
            "ExpressionLanguageInjection": "ExpressionLanguageInjection",
            "JNDI Lookup": "NamingContextLookup",
            "Load Arbitrary Library": "ReflectiveCall",
        }

        timeout_h = str(task_config_info[self.key_timeout])

        tool_folder = (
            join(values.dir_main, "llm_symbolic") if self.locally_running else "/tool"
        )

        # start running
        self.timestamp_log_start()

        # self.write_file(
        #     [
        #         f"{self.dir_expr}src/container_scripts/PipelineCommandUtilPovRunner.java\n",
        #         f"{self.dir_expr}src/src/easy-test/src/test/java/PipelineCommandUtilFuzzer.java\n",
        #         f"{self.dir_expr}src/src/plugins/pipeline-util-plugin/src/main/java/io/jenkins/plugins/UtilPlug/UtilMain.java",
        #     ],
        #     join(self.dir_output, "sources.txt"),
        # )

        source_dir = join(self.dir_expr, "src", "src")
        self.run_command(
            f"bash -c 'find {source_dir} | grep \\\\.java$ >> {join(self.dir_output,'sources.txt')}'"
        )

        for harness in bug_info["harnesses"]:
            harness_dir = os.path.dirname(join(self.dir_expr, "src", harness["source"]))
            self.run_command(
                f"bash -c 'find {harness_dir} | grep \\\\.java$ >> {join(self.dir_output,'sources.txt')}'"
            )

        sanitizer_code = []
        for sanitizers in bug_info["sanitizers"]:
            for id, key in san_mapper.items():
                if id.lower() in sanitizers["name"].lower():
                    sanitizer_code.append(key)
                    break

        harness_java = join(self.dir_expr, "src", bug_info["harnesses"][0]["source"])
        magic_string = "src/main/java/"
        harness_class_name = harness_java[
            harness_java.index(magic_string) + len(magic_string) :
        ].replace("/", ".")[: -len(".java")]

        analysis_command = f"timeout -k 5m {timeout_h}h python3 -m tss.aicc.main -src {join(self.dir_expr,'src',bug_info['harnesses'][0]['source'])} -s {','.join(sanitizer_code)} -j 30 -l {join(self.dir_output,'sources.txt')} -d {self.dir_output} -c {harness_class_name}".format(
            timeout_h
        )
        openai_token = self.api_keys.get(self.key_openai_token, None)

        status = self.run_command(
            analysis_command,
            self.log_output_path,
            tool_folder,
            {"OPENAI_API_KEY": openai_token},
        )

        self.process_status(status)

        self.run_command(f"mkdir -p {join(self.dir_setup,'passing_inputs')}")
        
        self.run_command(f"mkdir -p {join(self.dir_setup,'dicts')}")

        self.run_command(
            f"bash -c 'cp -rf {join(self.dir_output)}/*_input.bin {join(self.dir_setup,'passing_inputs')}'"
        )
        
        self.run_command(
            f"bash -c 'cp -rf {join(self.dir_output)}/dict.txt {join(self.dir_setup,'dicts')}'"
        )

        self.write_json(
            [
                {
                    "analysis_output": [
                        {
                            "generator": "LLMSymbollic",
                            "confidence": 0.5,
                            "exploit_inputs": [
                                {"format": "raw", "dir": "failing_inputs"}
                            ],
                            "benign_inputs": [
                                {"format": "raw", "dir": "passing_inputs"}
                            ],
                        }
                    ]
                }
            ],
            join(self.dir_output, "meta-data.json"),
        )

        self.timestamp_log_end()
        self.emit_highlight("\t\t\tlog file: {0}".format(self.log_output_path))

    def save_artifacts(self, dir_info: Dict[str, str]) -> None:
        """
        Save useful artifacts from the repair execution
        output folder -> self.dir_output
        logs folder -> self.dir_logs
        The parent method should be invoked at last to archive the results
        """
        super(LLMSymbolic, self).save_artifacts(dir_info)

    def analyse_output(
        self, dir_info: DirectoryInfo, bug_id: str, fail_list: List[str]
    ) -> AnalysisToolStats:
        self.emit_normal("reading output")
        return self.stats
