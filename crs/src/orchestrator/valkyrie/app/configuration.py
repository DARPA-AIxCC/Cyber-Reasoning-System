import os
import sys
import json
from app import definitions, values, emitter, utilities


def read_arg(argument_list):
    emitter.normal("reading configuration values")
    if len(argument_list) > 0:
        for arg in argument_list:
            if definitions.ARG_DEBUG_MODE in arg:
                values.CONF_DEBUG = True
            elif definitions.ARG_CLONE_MODE in arg:
                values.CONF_CLONE = True
            elif definitions.ARG_PURGE_MODE in arg:
                values.CONF_PURGE = True
            elif definitions.ARG_CONF_FILE in arg:
                values.FILE_CONFIGURATION = str(arg).replace(
                    definitions.ARG_CONF_FILE, ""
                )
            elif definitions.ARG_PATCH_MODE in arg:
                values.CONF_PATCH_MODE = str(arg).replace(
                    definitions.ARG_PATCH_MODE, ""
                )
            elif definitions.ARG_TEST_ID_LIST in arg:
                values.CONF_TEST_ID_LIST = json.loads(
                    str(arg).replace(definitions.ARG_TEST_ID_LIST, "") or "[]"
                )
            elif definitions.ARG_BIN_PATH in arg:
                values.CONF_BIN_PATH = str(arg).replace(definitions.ARG_BIN_PATH, "")
            elif definitions.ARG_SOURCE_FILE in arg:
                values.CONF_SOURCE_FILE = str(arg).replace(
                    definitions.ARG_SOURCE_FILE, ""
                )

            elif definitions.ARG_PATCH_DIR in arg:
                values.CONF_PATCH_DIR = str(arg).replace(definitions.ARG_PATCH_DIR, "")
            elif definitions.ARG_PATCH_FILE in arg:
                values.CONF_PATCH_FILE = str(arg).replace(
                    definitions.ARG_PATCH_FILE, ""
                )
            elif definitions.ARG_LIMIT in arg:
                values.CONF_LIMIT = int(arg.replace(definitions.ARG_LIMIT, ""))
            elif definitions.ARG_TEST_TIMEOUT in arg:
                values.CONF_TEST_TIMEOUT = int(
                    arg.replace(definitions.ARG_TEST_TIMEOUT, "")
                )
            elif definitions.ARG_TIMEOUT in arg:
                values.CONF_TIMEOUT = int(arg.replace(definitions.ARG_TIMEOUT, ""))
            elif definitions.ARG_TAG in arg:
                values.CONF_TAG = arg.replace(definitions.ARG_TAG, "")
            elif definitions.ARG_ONLY_VALIDATE in arg:
                values.CONF_ONLY_VALIDATE = True
            elif definitions.ARG_PARTITION in arg:
                values.CONF_PARTITION = True
            elif definitions.ARG_TEST_ORACLE in arg:
                values.CONF_TEST_ORACLE = str(arg).replace(
                    definitions.ARG_TEST_ORACLE, ""
                )
            elif definitions.ARG_TEST_SUITE in arg:
                values.CONF_TEST_SUITE = str(arg).replace(
                    definitions.ARG_TEST_SUITE, ""
                )
            elif definitions.ARG_TRACE_MODE in arg:
                values.CONF_TRACE_INDEX = int(
                    arg.replace(definitions.ARG_TRACE_MODE, "")
                )
            elif definitions.ARG_EXEC_MODE in arg:
                values.CONF_EXEC_INDEX = int(arg.replace(definitions.ARG_EXEC_MODE, ""))
            elif arg in ["--help", "-help", "-h"]:
                emitter.emit_help()
                exit(0)
            else:
                emitter.error("Unknown option: " + str(arg))
                emitter.emit_help()
                exit(1)


def read_conf_file():
    if values.FILE_CONFIGURATION:
        emitter.normal("reading configuration values form configuration file")
        emitter.note("\t[file] " + values.FILE_CONFIGURATION)
        # logger.information(values.FILE_CONFIGURATION)
        if not os.path.exists(values.FILE_CONFIGURATION):
            emitter.error("[NOT FOUND] Configuration file " + values.FILE_CONFIGURATION)
            exit()
        if os.path.getsize(values.FILE_CONFIGURATION) == 0:
            emitter.error("[EMPTY] Configuration file " + values.FILE_CONFIGURATION)
            exit()
        with open(values.FILE_CONFIGURATION, "r") as conf_file:
            configuration_list = [i.strip() for i in conf_file.readlines()]

        for configuration in configuration_list:
            if definitions.CONF_BIN_PATH in configuration:
                values.CONF_BIN_PATH = configuration.replace(
                    definitions.CONF_BIN_PATH, ""
                )
            elif definitions.CONF_PATCH_DIR in configuration:
                values.CONF_PATCH_DIR = configuration.replace(
                    definitions.CONF_PATCH_DIR, ""
                )
            elif definitions.CONF_OUTPUT_DIR in configuration:
                values.CONF_OUTPUT_DIR = configuration.replace(
                    definitions.CONF_OUTPUT_DIR, ""
                )
            elif definitions.CONF_SOURCE_FILE in configuration:
                values.CONF_SOURCE_FILE = configuration.replace(
                    definitions.CONF_SOURCE_FILE, ""
                )
            elif definitions.CONF_SOURCE_DIR in configuration:
                values.CONF_SOURCE_DIR = configuration.replace(
                    definitions.CONF_SOURCE_DIR, ""
                )
            elif definitions.CONF_TEST_ORACLE in configuration:
                values.CONF_TEST_ORACLE = configuration.replace(
                    definitions.CONF_TEST_ORACLE, ""
                )
            elif definitions.CONF_TEST_SUITE in configuration:
                values.CONF_TEST_SUITE = configuration.replace(
                    definitions.CONF_TEST_SUITE, ""
                )
            elif definitions.CONF_CONFIG_SCRIPT in configuration:
                values.CONF_CONFIG_SCRIPT = configuration.replace(
                    definitions.CONF_CONFIG_SCRIPT, ""
                )
            elif definitions.CONF_PATCH_COMMAND in configuration:
                values.CONF_PATCH_COMMAND = configuration.replace(
                    definitions.CONF_PATCH_COMMAND, ""
                )
            elif definitions.CONF_PATCH_SCRIPT in configuration:
                values.CONF_PATCH_SCRIPT = configuration.replace(
                    definitions.CONF_PATCH_SCRIPT, ""
                )
            elif definitions.CONF_RESET_COMMAND in configuration:
                values.CONF_RESET_COMMAND = configuration.replace(
                    definitions.CONF_RESET_COMMAND, ""
                )
            elif definitions.CONF_RESET_SCRIPT in configuration:
                values.CONF_RESET_SCRIPT = configuration.replace(
                    definitions.CONF_RESET_SCRIPT, ""
                )
            elif definitions.CONF_BUILD_SCRIPT in configuration:
                values.CONF_BUILD_SCRIPT = configuration.replace(
                    definitions.CONF_BUILD_SCRIPT, ""
                )
            elif definitions.CONF_PVT_TEST_SCRIPT in configuration:
                values.CONF_PVT_TEST_SCRIPT = configuration.replace(
                    definitions.CONF_PVT_TEST_SCRIPT, ""
                )
            elif definitions.CONF_PUB_TEST_SCRIPT in configuration:
                values.CONF_PUB_TEST_SCRIPT = configuration.replace(
                    definitions.CONF_PUB_TEST_SCRIPT, ""
                )
            elif definitions.CONF_ADV_TEST_SCRIPT in configuration:
                values.CONF_ADV_TEST_SCRIPT = configuration.replace(
                    definitions.CONF_ADV_TEST_SCRIPT, ""
                )

            elif definitions.CONF_TEST_ID_LIST in configuration:
                values.CONF_TEST_ID_LIST = json.loads(
                    configuration.replace(definitions.CONF_TEST_ID_LIST, "") or "[]"
                )
            elif definitions.CONF_PATCH_MODE in configuration:
                values.CONF_PATCH_MODE = configuration.replace(
                    definitions.CONF_PATCH_MODE, ""
                )
            elif definitions.CONF_TRACE_MODE in configuration:
                values.CONF_TRACE_MODE = configuration.replace(
                    definitions.CONF_TRACE_MODE, ""
                )
            elif definitions.CONF_TEST_TIMEOUT in configuration:
                values.CONF_TEST_TIMEOUT = int(
                    configuration.replace(definitions.CONF_TEST_TIMEOUT, "")
                )
            elif definitions.CONF_TIMEOUT in configuration:
                values.CONF_TIMEOUT = int(
                    configuration.replace(definitions.CONF_TIMEOUT, "")
                )
            elif definitions.CONF_PATCH_LIMIT in configuration:
                values.CONF_PATCH_LIMIT = int(
                    configuration.replace(definitions.CONF_PATCH_LIMIT, "")
                )
            elif definitions.CONF_PATCH_PER_DIR_LIMIT in configuration:
                values.CONF_PATCH_PER_DIR_LIMIT = int(
                    configuration.replace(definitions.CONF_PATCH_PER_DIR_LIMIT, "")
                )
            elif definitions.CONF_TAG in configuration:
                values.CONF_TAG = configuration.replace(definitions.CONF_TAG, "")
            elif definitions.CONF_EXEC_MODE in configuration:
                values.CONF_EXEC_MODE = configuration.replace(
                    definitions.CONF_EXEC_MODE, ""
                )
            elif definitions.CONF_LIMIT in configuration:
                if not values.CONF_LIMIT:
                    values.CONF_LIMIT = int(
                        configuration.replace(definitions.CONF_LIMIT, "")
                    )


def validate_configuration():
    emitter.normal("validating parameter values")
    show_help = False
    if (
        not values.CONF_BIN_PATH
        and not values.FILE_CONFIGURATION
        and not values.CONF_TEST_SUITE
    ):
        emitter.emit_help()
        exit()
    if values.CONF_BIN_PATH and os.path.isfile(values.CONF_BIN_PATH):
        values.CONF_BIN_PATH = os.path.abspath(values.CONF_BIN_PATH)
    else:
        values.CONF_BIN_PATH = None

    if values.CONF_PATCH_DIR and os.path.isdir(values.CONF_PATCH_DIR):
        values.CONF_PATCH_DIR = os.path.abspath(values.CONF_PATCH_DIR)
    else:
        values.CONF_PATCH_DIR = None

    if values.CONF_PATCH_FILE and os.path.isfile(values.CONF_PATCH_FILE):
        values.CONF_PATCH_FILE = os.path.abspath(values.CONF_PATCH_FILE)
    else:
        values.CONF_PATCH_FILE = None

    if values.CONF_TEST_ORACLE and os.path.isfile(values.CONF_TEST_ORACLE):
        values.CONF_TEST_ORACLE = os.path.abspath(values.CONF_TEST_ORACLE)
    else:
        values.CONF_TEST_ORACLE = None

    if not values.CONF_TEST_SUITE and not values.CONF_PUB_TEST_SCRIPT:
        if not values.CONF_BIN_PATH and not values.CONF_TEST_ORACLE:
            show_help = True
            emitter.error("[invalid] binary/test-oracle is missing")

    if not values.CONF_PATCH_DIR and not values.CONF_PATCH_FILE:
        show_help = True
        emitter.error(
            "[invalid] {0}/{1} is missing".format(
                definitions.ARG_PATCH_DIR, definitions.ARG_PATCH_FILE
            )
        )

    if not values.CONF_TEST_ID_LIST:
        show_help = True
        emitter.error("[invalid] {0} is missing".format(definitions.ARG_TEST_ID_LIST))

    if values.CONF_TRACE_MODE:
        if values.CONF_TRACE_MODE not in list(definitions.OPTIONS_TRACE_MODE.values()):
            show_help = True
            emitter.error(
                "[invalid] {0} is not a valid option for {1}".format(
                    values.CONF_TRACE_MODE, definitions.CONF_TRACE_MODE
                )
            )

    if values.CONF_EXEC_MODE:
        if values.CONF_EXEC_MODE not in list(definitions.OPTIONS_EXEC_MODE.values()):
            show_help = True
            emitter.error(
                "[invalid] {0} is not a valid option for {1}".format(
                    values.CONF_EXEC_MODE, definitions.CONF_EXEC_MODE
                )
            )

    if values.CONF_PATCH_MODE:
        if values.CONF_PATCH_MODE not in definitions.OPTIONS_PATCH_MODE:
            show_help = True
            emitter.error(
                "[invalid] {0} is not a valid option for {1}/{2}".format(
                    values.CONF_PATCH_MODE,
                    definitions.ARG_PATCH_MODE,
                    definitions.CONF_PATCH_MODE,
                )
            )

    if values.CONF_TRACE_INDEX:
        if values.CONF_TRACE_INDEX not in definitions.OPTIONS_TRACE_MODE:
            show_help = True
            emitter.error(
                "Invalid option for "
                + definitions.ARG_TRACE_MODE.replace("=", "")
                + " : "
                + values.CONF_TRACE_INDEX
            )
        else:
            values.CONF_TRACE_MODE = definitions.OPTIONS_TRACE_MODE[
                values.CONF_TRACE_INDEX
            ]

    if values.CONF_EXEC_INDEX:
        if values.CONF_EXEC_INDEX not in definitions.OPTIONS_EXEC_MODE:
            show_help = True
            emitter.error(
                "Invalid option for "
                + definitions.ARG_EXEC_MODE.replace("=", "")
                + " : "
                + values.CONF_EXEC_INDEX
            )
        else:
            values.CONF_EXEC_MODE = definitions.OPTIONS_EXEC_MODE[
                values.CONF_EXEC_INDEX
            ]
    if values.CONF_PARTITION:
        values.DEFAULT_PARTITION = values.CONF_PARTITION

    if show_help:
        emitter.emit_help()
        exit(1)


def update_configuration():
    emitter.normal("updating configuration values")
    if values.CONF_BIN_PATH:
        if not os.path.isfile(values.CONF_BIN_PATH):
            utilities.error_exit(
                "[error] invalid binary path: {0}".format(values.CONF_BIN_PATH)
            )
    if values.CONF_EXEC_MODE:
        values.DEFAULT_EXEC_MODE = values.CONF_EXEC_MODE
    if values.CONF_PATCH_MODE:
        values.DEFAULT_PATCH_MODE = values.CONF_PATCH_MODE
    if values.CONF_LIMIT:
        values.DEFAULT_LIMIT = values.CONF_LIMIT
    if values.CONF_TEST_TIMEOUT:
        values.DEFAULT_TEST_TIMEOUT = values.CONF_TEST_TIMEOUT
    if values.CONF_TIMEOUT:
        values.DEFAULT_TIMEOUT = values.CONF_TIMEOUT
    if values.CONF_PATCH_PER_DIR_LIMIT:
        values.DEFAULT_LIMIT_PER_DIR = values.CONF_PATCH_PER_DIR_LIMIT
    if values.CONF_PATCH_LIMIT:
        values.DEFAULT_LIMIT = values.CONF_PATCH_LIMIT
    if values.CONF_TAG:
        values.DEFAULT_TAG = values.CONF_TAG
    if values.CONF_TRACE_MODE:
        values.DEFAULT_TRACE_MODE = values.CONF_TRACE_MODE
    if values.CONF_ONLY_VALIDATE:
        values.DEFAULT_ONLY_VALIDATE = values.CONF_ONLY_VALIDATE
    if values.CONF_TEST_ORACLE:
        if not os.path.isfile(values.CONF_TEST_ORACLE):
            utilities.error_exit(
                "[error] invalid test oracle: {0}".format(values.CONF_TEST_ORACLE)
            )
    if values.CONF_TEST_SUITE:
        if not os.path.isfile(values.CONF_TEST_SUITE):
            utilities.error_exit(
                "[error] invalid test suite: {0}".format(values.CONF_TEST_SUITE)
            )
    if values.CONF_PUB_TEST_SCRIPT:
        if not os.path.isfile(values.CONF_PUB_TEST_SCRIPT):
            utilities.error_exit(
                "[error] invalid public test script: {0}".format(
                    values.CONF_PUB_TEST_SCRIPT
                )
            )

    if values.CONF_PVT_TEST_SCRIPT:
        if not os.path.isfile(values.CONF_PVT_TEST_SCRIPT):
            utilities.error_exit(
                "[error] invalid private test script: {0}".format(
                    values.CONF_PVT_TEST_SCRIPT
                )
            )
    if values.CONF_ADV_TEST_SCRIPT:
        if not os.path.isfile(values.CONF_ADV_TEST_SCRIPT):
            utilities.error_exit(
                "[error] invalid adversarial test script: {0}".format(
                    values.CONF_ADV_TEST_SCRIPT
                )
            )
    if values.CONF_PATCH_DIR:
        if not os.path.isdir(values.CONF_PATCH_DIR):
            utilities.error_exit(
                "[error] invalid patch directory: {0}".format(values.CONF_PATCH_DIR)
            )
    if values.CONF_PATCH_FILE:
        if not os.path.isfile(values.CONF_PATCH_FILE):
            utilities.error_exit(
                "[error] invalid patch file: {0}".format(values.CONF_PATCH_FILE)
            )
    sys.setrecursionlimit(values.DEFAULT_STACK_SIZE)


def check_dependencies():
    emitter.normal("checking dependencies")
    status = os.system("which gdb > /dev/null 2>&1")
    if status != 0:
        emitter.warning("[warning] gdb not found")

    if not values.DEFAULT_ONLY_VALIDATE:
        status = os.system("which e9afl > /dev/null 2>&1")
        if status != 0:
            utilities.error_exit("[error] e9afl not found")
        if values.DEFAULT_PATCH_MODE == "rewrite" or values.DEFAULT_TRACE_MODE == "e9":
            status = os.system("which e9tool > /dev/null 2>&1")
            if status != 0:
                utilities.error_exit("[error] e9tool not found")
            status = os.system("which afl-showmap > /dev/null 2>&1")
            if status != 0:
                utilities.error_exit("[error] afl-showmap not found")


def print_configuration():
    if values.FILE_CONFIGURATION:
        emitter.configuration("config_file", values.FILE_CONFIGURATION)
    emitter.configuration("timeout", values.DEFAULT_TIMEOUT)
    emitter.configuration("tag", values.DEFAULT_TAG)
    emitter.configuration("test timeout", values.DEFAULT_TEST_TIMEOUT)
    emitter.configuration("test id list", values.CONF_TEST_ID_LIST)
    emitter.configuration("test oracle", values.CONF_TEST_ORACLE)
    emitter.configuration("test suite", values.CONF_TEST_SUITE)
    emitter.configuration("execution mode", values.DEFAULT_EXEC_MODE)
    emitter.configuration("patch command", values.CONF_PATCH_COMMAND)
    emitter.configuration("patch script", values.CONF_PATCH_SCRIPT)
    emitter.configuration("reset command", values.CONF_RESET_COMMAND)
    emitter.configuration("reset script", values.CONF_RESET_SCRIPT)
