import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from os import PathLike, makedirs
from pathlib import Path
from pprint import pprint
from queue import SimpleQueue
from subprocess import CalledProcessError, run

import pydot

JOERN_DIR = Path(__file__).parent.parent.parent.joinpath("joern-cli")
if not JOERN_DIR.is_dir():
    print(f"{JOERN_DIR!s} is not a directory", file=sys.stderr)
    exit(0)


def parse_ddg_tag(tag: str) -> tuple[str, int]:
    pattern = r"<\((.*?),(.*)<SUB>(\d+)</SUB>>"

    if match := re.match(pattern, tag, re.DOTALL):
        return match[1], match[2], int(match[3])

    print(f"cannot parse ddg result: {tag}")
    return None


class PdgGraph:
    def __init__(self, dot_content) -> None:
        self.ddg_forward_dependences = {}
        self.ddg_forward_labels = {}
        self.ddg_backward_dependences = {}
        self.ddg_backward_labels = {}
        self.cdg_predecessors = {}
        self.cdg_successors = {}
        self.cfg_predecessors = {}
        self.cfg_successors = {}
        self.linenum_citi = {}
        self.node2line = {}
        self.node2code = {}
        self.line2node = {}
        self.line2code = {}
        self.nodes = []
        self.edges = []
        self.parse_dot_to_pdg(dot_content)

    def parse_label(self, label):
        # match = re.match(r"\(([^,]+), ([^\)]+)\)<SUB>(\d+)</SUB>", label)
        pattern = r"\d+"
        match = re.findall(pattern, label)
        return match[-1] if len(match) > 0 else None

    def parse_dot_to_pdg(self, graph):
        # node_dict = {}  # position: code
        node_info_dict = {}  # node_id: [code, position, type]
        nodelist = graph[0].get_node_list()

        label = ""
        for node in nodelist:
            node_id = node.get_name()
            tempAttr = json.dumps(node.get_attributes())
            nodeAttr = json.loads(tempAttr)

            if "label" in nodeAttr:
                label = nodeAttr["label"]  # print colored(nodeAttr['label'], 'red')
                if lineno := self.parse_label(label):
                    self.node2line[node_id] = lineno
                    self.node2code[node_id] = label
                    self.line2code[lineno] = label
                    if lineno not in self.linenum_citi:
                        self.linenum_citi[lineno] = []
                    self.linenum_citi[lineno].append(node_id)
                    self.node2line[node_id] = lineno
                else:
                    print("Error: ", label)

        edge_dict = {}  # src: [[dest,label],[dest,label], ...]
        edgelist = graph[0].get_edge_list()
        for e in edgelist:
            # edge_attr = e.get_attributes()
            source = e.get_source()
            destination = e.get_destination()
            # dataflow dependency
            if destination not in self.ddg_backward_dependences:
                self.ddg_backward_dependences[destination] = []
            self.ddg_backward_dependences[destination].append(source)

            if source not in self.ddg_forward_dependences:
                self.ddg_forward_dependences[source] = []

            self.ddg_forward_dependences[source].append(destination)
            # recording data dependency variable
            forward_edge_key = self.node2line[f"{source}"]
            backward_edge_key = self.node2line[f"{destination}"]
            if forward_edge_key not in self.ddg_forward_labels:
                self.ddg_forward_labels[forward_edge_key] = []
            self.ddg_forward_labels[forward_edge_key].append([label, backward_edge_key])
            if backward_edge_key not in self.ddg_backward_labels:
                self.ddg_backward_labels[backward_edge_key] = []
            self.ddg_backward_labels[backward_edge_key].append(
                [label, forward_edge_key]
            )
        return (edge_dict, node_info_dict)

    def __str__(self):
        content = ""
        content += (
            "\n".join(
                [
                    f"({self.node2line[edge[0]]},{edge[1]},{self.node2line[edge[2]]})"
                    for edge in self.edges
                ]
            )
            + "\n"
        )
        return content


def GetPrePath(line, pdg, max_depth=3):
    depth = 0
    path_lines = {str(line): ["citi", depth]}
    while depth < max_depth:
        depth += 1
        GetPreiter(path_lines, pdg, depth)
    return path_lines


def GetPreiter(current_lines, pdg, depth):
    pre_lines = {}
    for current_line in current_lines:
        pre_items = GetPreNodes(current_line, pdg)
        for pre_item in pre_items:
            pre_line = pre_item[0]
            pre_type = pre_item[1]
            if pre_line.isdigit() and pre_line not in pre_lines:
                pre_lines[pre_line] = [pre_type, depth]

    for line, value in pre_lines.items():
        if line not in current_lines:
            current_lines[line] = value


def GetPreNodes(line, pdg):
    pre_lines = []
    if line in pdg.linenum_citi:
        for node_id in pdg.linenum_citi[line]:
            if ddg_pre_nodes := pdg.ddg_backward_dependences.get(str(node_id)):
                for ddg_node_id in ddg_pre_nodes:
                    if ddg_node_id in pdg.node2line:
                        pre_line = pdg.node2line[ddg_node_id]
                        pre_lines.append([pre_line, "ddg"])
        # CFG forward
        if line in pdg.cfg_predecessors:
            cfg_pre_lines = pdg.cfg_predecessors[line]
            for cfg_pre_line, d_type in cfg_pre_lines.items():
                pre_lines.append([cfg_pre_line, d_type])
        # CDG forward
        if line in pdg.cdg_predecessors:
            cdg_pre_lines = pdg.cdg_predecessors[line]
            for cdg_pre_line, d_type in cdg_pre_lines.items():
                pre_lines.append([cdg_pre_line, d_type])
    return pre_lines


def execute_command(command: list[str]) -> None:
    try:
        run(
            command,
            text=True,
            capture_output=True,
            check=True,
        )
    except CalledProcessError as e:
        print(e.stderr, file=sys.stderr)
        raise


class Slicer:
    def __init__(
        self,
        cp_src: list | None = None,
        data_dir: str | PathLike | None = None,
        num_processes: int = 1,
    ):
        self.data_dir = data_dir or ".data/"

        makedirs(self.data_dir, exist_ok=True)

        cp_src = cp_src or []

        def generate_data(filename):
            hv = hashlib.sha1(filename.encode("utf-8")).hexdigest()
            bin_file = os.path.join(self.data_dir, f"{hv}.bin")
            dots_dir = self.target_dots_dir(filename)

            self.cpg_gen(filename, bin_file)
            self.dot_gen(bin_file, dots_dir)

        files = [f for f in cp_src if not os.path.exists(self.target_dots_dir(f))]

        # each thread will start a process
        with ThreadPoolExecutor(max_workers=num_processes) as executor:
            executor.map(generate_data, files)

    def target_dots_dir(self, filename):
        hv = hashlib.sha1(filename.encode("utf-8")).hexdigest()
        return os.path.join(self.data_dir, f"{hv}_dots")

    def cpg_gen(self, filename, save_to):
        joern_parse = str(JOERN_DIR.joinpath("joern-parse"))

        # save_to = os.path.join(self.data_dir, output_name)

        cmd = [joern_parse, filename, "-o", save_to]
        execute_command(cmd)

    def dot_gen(self, bin_file, dots_dir):
        joern_export = str(JOERN_DIR.joinpath("joern-export"))

        # save_to = os.path.join(self.data_dir, output_name)

        cmd = [
            joern_export,
            bin_file,
            "--repr",
            "ddg",
            "--out",
            dots_dir,
        ]
        execute_command(cmd)

    def do_slice_by_line(self, pdg_graph, lineno):
        return self.slicing(lineno, pdg_graph)

    def slicing(self, linenums, pdg_graph):
        expand_queue = SimpleQueue()
        sliced_lines = set()
        expand_node = set()
        # add citi_line in list
        if isinstance(linenums, list):
            for linenum in linenums:
                expand_queue.put((str(linenum), 0, "citi"))  # depth = 0
        else:
            expand_queue.put((str(linenums), 0, "citi"))  # depth = 0
        # add filter to decide what dependence to expand?
        # what is the depth of dependence to expand?
        while not expand_queue.empty():
            # save line nums of the current node.
            cur_line, depth, dtype = expand_queue.get()
            if depth >= 2:
                break
            sliced_lines.add((cur_line, dtype))

            if cur_line in pdg_graph.linenum_citi:
                for node_id in pdg_graph.linenum_citi[cur_line]:
                    expand_node.add((node_id, depth))
                    # DDG backward slice
                    if data_dependecies := pdg_graph.ddg_backward_dependences.get(
                        str(node_id)
                    ):
                        for dd_node_id in data_dependecies:
                            expand_node.add((dd_node_id, depth + 1))
                            if dd_node_id not in pdg_graph.node2line:
                                continue
                            node_linenum = pdg_graph.node2line[dd_node_id]
                            # if cut off the slicing to a certain line
                            if (
                                str(node_linenum) not in sliced_lines
                            ):  # and int(node_linenum) < int(cur_line) :
                                expand_queue.put((str(node_linenum), depth + 1, "ddg"))
                    # DDG forward slice
                    # 1. backward
                    if pres := pdg_graph.cdg_predecessors.get(str(node_id)):
                        for pre_id in pres:
                            expand_node.add((pre_id, depth + 1))
                            if pre_id not in pdg_graph.node2line:
                                continue
                            node_linenum = pdg_graph.node2line[pre_id]
                            if (
                                str(node_linenum) not in sliced_lines
                            ):  # and int(node_linenum) < int(cur_line):
                                expand_queue.put((str(node_linenum), depth + 1, "cdg"))

        expand_node = list(expand_node)
        expand_node.sort(key=lambda x: (x[1], x[0]))
        sliced_lines = list(sliced_lines)
        sliced_lines.sort(key=lambda x: x[0])
        return expand_node, sliced_lines

    def ddg_forward_slice(self, linenums, pdg_graph):
        expand_queue = SimpleQueue()
        sliced_lines = set()
        expand_node = set()
        # search method start line
        for k, v in pdg_graph.line2code.items():
            if v.find("<(PARAM") != -1:
                expand_queue.put((str(k), 0, "citi"))  # depth = 0
                break
        # add citi_line in listdir
        # if isinstance(linenums, list):
        #    for linenum in linenums:
        #        expand_queue.put((str(linenum), 0, "citi"))  # depth = 0
        # else:
        #    expand_queue.put((str(linenums), 0, "citi"))  # depth = 0
        while not expand_queue.empty():
            cur_line, depth, dtype = expand_queue.get()
            if depth >= 2:
                break
            sliced_lines.add((cur_line, dtype))
            if cur_line in pdg_graph.linenum_citi:
                for node_id in pdg_graph.linenum_citi[cur_line]:
                    expand_node.add((node_id, depth))
                    # DDG backward slice
                    if data_dependecies := pdg_graph.ddg_forward_dependences.get(
                        str(node_id)
                    ):
                        for dd_node_id in data_dependecies:
                            expand_node.add((dd_node_id, depth + 1))
                            if dd_node_id not in pdg_graph.node2line:
                                continue
                            node_linenum = pdg_graph.node2line[dd_node_id]
                            # if cut off the slicing to a certain line
                            if (
                                str(node_linenum) not in sliced_lines
                            ):  # and int(node_linenum) < int(cur_line) :
                                expand_queue.put((str(node_linenum), depth + 1, "ddg"))
                        # DDG forward slice

        expand_node = list(expand_node)
        expand_node.sort(key=lambda x: (x[1], x[0]))
        sliced_lines = list(sliced_lines)
        sliced_lines.sort(key=lambda x: x[0])
        selected_nodes = []
        selected_lines = []
        for node in expand_node:
            segments = parse_ddg_tag(pdg_graph.node2code[node[0]])
            if segments is None:
                continue
            the_type = segments[0]
            if the_type.endswith("assignment") or the_type.endswith("when"):
                selected_nodes.append(node)
        return selected_nodes
        # print(pdg_graph.node2line[node[0]])

    def slice(self, filename: str, method_name: str, line_number: int) -> list[str]:
        # tree-sitter is 0-based, while joern line-number is 1-based
        line_number += 1

        # select a graph dot file using method name
        dots_dir = self.target_dots_dir(filename)
        all_dot_files = os.listdir(dots_dir)
        graph_data_by_method = {}
        for fn in all_dot_files:
            tmp_graph_data = pydot.graph_from_dot_file(os.path.join(dots_dir, fn))
            assert tmp_graph_data is not None
            g_name = tmp_graph_data[0].get_name().strip('"')
            graph_data_by_method[g_name] = tmp_graph_data

        try:
            # slicer
            graph_data = graph_data_by_method.get(method_name)

            if graph_data is None:
                return []
            pdg = PdgGraph(graph_data)
            # if line no is -1, slice the whole method, otherwise slice the line
            if line_number == -1:
                ddg_nodes = self.ddg_forward_slice(line_number, pdg)
            else:
                ddg_nodes, _ = self.do_slice_by_line(pdg, line_number)
            ddg_nodes = self.ddg_forward_slice(line_number, pdg)
            node2code = pdg.node2code

            return [node2code[node[0]] for node in ddg_nodes]
        except KeyError:
            return []


def quote_text(text):
    if ":" in text and not (text.startswith('"') and text.endswith('"')):
        return f'"{text}"'
    return text


def test_slice():
    fuzzer_file = "/home/user/shared/sym-llm/challenge-002-jenkins-cp/src/easy-test/src/test/java/PipelineCommandUtilFuzzer.java"
    plugin_file = "/home/user/shared/sym-llm/challenge-002-jenkins-cp/src/plugins/pipeline-util-plugin/src/main/java/io/jenkins/plugins/UtilPlug/UtilMain.java"

    cp_src_files = [fuzzer_file, plugin_file]
    slicer = Slicer(cp_src_files)

    slice_parts = slicer.slice(fuzzer_file, "fuzzerTestOneInput", 23)
    pprint(slice_parts)
    return 0


if __name__ == "__main__":
    test_slice()
