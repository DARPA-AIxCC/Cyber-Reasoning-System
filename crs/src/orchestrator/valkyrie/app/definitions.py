import os
from os.path import dirname

DIR_CWD = os.getcwd()
DIR_MAIN = dirname(dirname(os.path.realpath(__file__)))
DIR_RESULT = DIR_MAIN + "/results"
DIR_EXPERIMENT = DIR_MAIN + "/experiments"
DIR_LOGS = DIR_MAIN + "/logs"
DIRECTORY_OUTPUT = DIR_MAIN + "/output"
DIRECTORY_LIB = DIR_MAIN + "/lib"
FILE_MAIN_LOG = ""
FILE_ERROR_LOG = DIR_LOGS + "/log-error"
FILE_LAST_LOG = DIR_LOGS + "/log-latest"
FILE_MAKE_LOG = DIR_LOGS + "/log-make"
FILE_COMMAND_LOG = DIR_LOGS + "/log-command"
FILE_ANALYSIS_LOG = DIR_LOGS + "/log-analysis"
FILE_GDB_PATCH_SCRIPT = "/tmp/gdb_patch_script"
FILE_GDB_SNAPSHOT_SCRIPT = "/tmp/gdb_script_snapshot"
FILE_GDB_FRONTEND = "/tmp/gdb_frontend"
FILE_INVALID_LIST = DIR_CWD + "/invalid_list"
FILE_COMPILE_LIST = DIR_CWD + "/compile_list"
FILE_PATCH_SCORE = DIR_CWD + "/patch-score"
FILE_RESULT_JSON = DIR_CWD + "/result.json"


# ----------------- KEY DEFINITIONS -------------------

KEY_DURATION_TOTAL = "run-time"
KEY_DURATION_BOOTSTRAP = "bootstrap"
KEY_DURATION_BUILD = "build"
KEY_DURATION_INITIALIZATION = "initialization"
KEY_DURATION_REPAIR = "repair"

KEY_BUG_ID = "bug_id"
KEY_BENCHMARK = "benchmark"
KEY_ID = "id"
KEY_SUBJECT = "subject"
KEY_FIX_FILE = "source_file"
KEY_FIX_LINE = "line_number"
KEY_PASSING_TEST = "passing_test"
KEY_FAILING_TEST = "failing_test"
KEY_CONFIG_TIMEOUT = "timeout"
KEY_CONFIG_FIX_LOC = "fault_location"
KEY_CONFIG_TEST_RATIO = "passing_test_ratio"
KEY_BINARY_PATH = "binary_path"
KEY_COUNT_NEG = "count_neg"
KEY_COUNT_POS = "count_pos"
KEY_CRASH_CMD = "crash_input"


ARG_DEBUG_MODE = "--debug"
ARG_CLONE_MODE = "--clone"
ARG_PURGE_MODE = "--purge"
ARG_BIN_PATH = "--binary="
ARG_CONF_FILE = "--conf="
ARG_SOURCE_FILE = "--source="
ARG_PATCH_DIR = "--patch-dir="
ARG_PATCH_FILE = "--patch-file="
ARG_TEST_ID_LIST = "--test-id-list="
ARG_TEST_ORACLE = "--test-oracle="
ARG_PRIVATE_TEST_SUITE = "--pvt-test-suite="
ARG_ADVERSARIAL_TEST_SUITE = "--adv-test-suite="
ARG_TEST_SUITE = "--test-suite="
ARG_PATCH_MODE = "--patch-mode="
ARG_TRACE_MODE = "--trace-mode="
ARG_EXEC_MODE = "--exec="
ARG_LIMIT = "--limit="
ARG_ONLY_VALIDATE = "--only-validate"
ARG_TEST_TIMEOUT = "--test-timeout="
ARG_PARTITION = "--partition"
ARG_TIMEOUT = "--timeout="
ARG_TAG = "--tag="


CONF_DEBUG_MODE = "debug:"
CONF_BIN_PATH = "binary:"
CONF_SOURCE_FILE = "source_file:"
CONF_SOURCE_DIR = "source_dir:"
CONF_OUTPUT_DIR = "output_dir:"
CONF_PATCH_DIR = "patch_dir:"
CONF_TEST_ID_LIST = "test_id_list:"
CONF_TEST_ORACLE = "test_oracle:"
CONF_PUB_TEST_SCRIPT = "pub_test_script:"
CONF_PVT_TEST_SCRIPT = "pvt_test_script:"
CONF_ADV_TEST_SCRIPT = "adv_test_script:"
CONF_BUILD_SCRIPT = "build_script:"
CONF_CONFIG_SCRIPT = "config_script:"
CONF_PATCH_COMMAND = "patch_command:"
CONF_PATCH_SCRIPT = "patch_script:"
CONF_RESET_COMMAND = "reset_command:"
CONF_RESET_SCRIPT = "reset_script:"
CONF_PATCH_MODE = "patch_mode:"
CONF_TRACE_MODE = "trace_mode:"
CONF_EXEC_MODE = "exec_mode:"
CONF_LIMIT = "limit:"
CONF_TEST_TIMEOUT = "test_timeout:"
CONF_TEST_SUITE = "test_suite:"
CONF_TIMEOUT = "timeout:"
CONF_TAG = "tag:"
CONF_PATCH_LIMIT = "patch_limit:"
CONF_PATCH_PER_DIR_LIMIT = "patch_per_dir_limit:"

FILE_META_DATA = None
FILE_CONFIGURATION = ""
FILE_OUTPUT_LOG = ""
FILE_SETUP_LOG = ""
FILE_INSTRUMENT_LOG = ""

VALUE_OPERATE_MODE_REWRITE = "rewrite"
VALUE_OPERATE_MODE_COMPILE = "compile"
VALUE_OPERATE_MODE_GDB = "gdb"

OPTIONS_PATCH_MODE = [
    VALUE_OPERATE_MODE_REWRITE,
    VALUE_OPERATE_MODE_COMPILE,
    VALUE_OPERATE_MODE_GDB,
]
OPTIONS_EXEC_MODE = {0: "sequential", 1: "semi-parallel", 2: "parallel"}
OPTIONS_TRACE_MODE = {0: "gdb", 1: "e9"}
