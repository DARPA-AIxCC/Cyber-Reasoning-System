from __future__ import annotations

import asyncio
import hashlib
import json
import os
from random import randint
import re
import subprocess
import sys
from collections import defaultdict, deque
from collections.abc import Generator
from dataclasses import dataclass
from functools import cache
from itertools import chain, zip_longest
from os import PathLike
from os.path import isfile
from pathlib import Path
from subprocess import CalledProcessError, run
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Optional

import click
import tree_sitter_java as tsjava
from litellm import completion
from tree_sitter import Language
from tree_sitter import Node as TSNode
from tree_sitter import Parser, Tree

from tss.aicc.definitions import HOOKS, PROMPT_OUTPUT_REQ, make_prompt_header
from tss.aicc.slice import Slicer
from tss.aicc.ts_query import collect_string_literals

JAVA_LANGUAGE = Language(tsjava.language())

TS_DICT_QUERY = """
[
  (character_literal)
  (string_literal)
] @string
(escape_sequence) @string.escape
"""

# header of the prompt


CALL_GRAPH_GENERATOR_JAR = str(
    Path(__file__)
    .resolve()
    .parent.parent.parent.joinpath(
        "call-graph-generator", "target", "call-graph-generator.jar"
    )
)
assert isfile(CALL_GRAPH_GENERATOR_JAR), f"{CALL_GRAPH_GENERATOR_JAR} is not a file"


ENTRY = dict()


@dataclass
class Predicate:
    ts_node: TSNode
    is_true: bool
    position: FilePos
    type: str
    scope: str  # which method does this predicate belong to

    def description(self) -> str:
        truth_value = "true" if self.is_true else "false"
        return f"({self.ts_node.text.decode()}) == {truth_value}"


@dataclass
class CgNode:
    qualifiedClassName: str
    methodName: str
    argTypes: list[str]
    argNames: list[str]

    def __str__(self) -> str:
        arg_list = ", ".join(f"{t} {n}" for t, n in zip(self.argTypes, self.argNames))
        return f"{self.qualifiedClassName}::{self.methodName}({arg_list})"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, CgNode)
            and self.qualifiedClassName == other.qualifiedClassName
            and self.methodName == other.methodName
            and self.argTypes == other.argTypes
        )

    def __hash__(self) -> int:
        return hash((self.qualifiedClassName, self.methodName, tuple(self.argTypes)))


@dataclass(eq=True, frozen=False)
class FilePos:
    line: int
    endLine: int
    column: int
    endColumn: int
    start: int
    end: int
    file: str

    def to_tsnode(self) -> TSNode | None:
        pos = self
        content = cached_read_file(pos.file)

        parser = Parser()
        parser.language = JAVA_LANGUAGE
        tree = parser.parse(content)

        for tsnode in self.traverse_tree(tree):
            if tsnode.start_byte == pos.start and tsnode.end_byte == pos.end:
                return tsnode

        print(
            f"Warning: failed to find a treesitter node at: {pos.file}, bytes [{pos.start}, {pos.end})",
            file=sys.stderr,
        )
        return None

    @staticmethod
    def traverse_tree(tree: Tree) -> Generator[TSNode, None, None]:
        cursor = tree.walk()

        visited_children = False
        while True:
            if not visited_children:
                yield cursor.node
                if not cursor.goto_first_child():
                    visited_children = True
            elif cursor.goto_next_sibling():
                visited_children = False
            elif not cursor.goto_parent():
                break


@dataclass
class CfgPath:
    node: CgNode
    position: FilePos
    predicates: list[Predicate]

    def add_predicate(self, predicate: Predicate) -> None:
        self.predicates.append(predicate)

    def get_predicate_dependencies(
        self, index: int, slicer: Slicer, arg_map: dict[str, str]
    ) -> list[str]:
        """Get the string representations of the dependencies of a predicate.

        Args:
            index: index of predicate
            slicer: slicer
            arg_map: mapping from formal parameter names to actual arguments for this method call

        Returns:
            list of string representations of the dependencies
        """
        result = []

        predicate = self.predicates[index]

        content = cached_read_file(self.position.file).decode().splitlines()
        line_numbers = self._get_dependent_line_numbers(predicate, slicer)

        result.extend(content[line_no] for line_no in line_numbers)

        return result

    def _get_dependent_line_numbers(
        self, predicate: Predicate, slicer: Slicer
    ) -> list[int]:
        predicate_line_no, _ = predicate.ts_node.start_point
        method_name = self.node.methodName
        # force to use param line and forward dataslices returned
        # if predicate.ts_node.type == "method_invocation":
        #    print('slciing acorss scope')
        #    return []
        # if this is a method_invocation, then slice it's implementation, otherwise only get it's dependencies
        if predicate.type == "method_invocation":
            all_names = find_identifiers(predicate.ts_node)
            if len(all_names) == 0:
                return []
            method_name = all_names[0]

            ddg = slicer.slice(self.position.file, method_name, predicate_line_no)
        else:
            ddg = slicer.slice(self.position.file, method_name, predicate_line_no)

        line_numbers = set()

        for x in ddg:
            the_type, dep_line_no = self._parse_ddg_tag(x)
            if the_type in ["METHOD", "PARAM", "METHOD_RETURN"]:
                continue
            line_numbers.add(dep_line_no)
        line_numbers.discard(predicate_line_no)
        return sorted(line_numbers)

    @classmethod
    def _parse_ddg_tag(cls, tag: str) -> tuple[str, int]:
        pattern = r"<\((.*?),(.*)<SUB>(\d+)</SUB>>"

        if match := re.match(pattern, tag, re.DOTALL):
            return match[1], int(match[3]) - 1

        raise RuntimeError(f"cannot parse ddg result: {tag}")


def find_identifiers(tsnode: TSNode) -> list[str]:
    identifiers = []
    for child in tsnode.children:
        if child.type == "identifier":
            idt = child.text.decode()
            if idt not in identifiers:
                identifiers.append(idt)
        else:
            identifiers.extend(find_identifiers(child))
    # in some Python versions, the order of the identifiers is not deterministic
    return identifiers


@dataclass
class Constraint:
    predicate_desc: str
    dependencies: list[str]


@dataclass
class IcfgPath:
    arg_maps: list[dict[str, str]]
    cfg_paths: list[CfgPath]

    hook_name: str
    hook_arg_map: dict[str, str]

    def compute_description(self, slicer: Slicer) -> str:
        return self._describe_constraints(
            [*self._collect_path_constraints(slicer), *self._collect_hook_constraints()]
        )

    def _collect_hook_constraints(self) -> list[Constraint]:
        constraints = []

        parser = Parser()
        parser.language = JAVA_LANGUAGE
        if self.hook_name not in HOOKS:
            print(f"warning: hook {self.hook_name} not found", file=sys.stderr)
            return []
        for predicate_desc in HOOKS[self.hook_name]["conditions"]:
            dependencies = []

            ts_node = parser.parse(predicate_desc.encode()).root_node
            identifiers = find_identifiers(ts_node)
            for ident in identifiers:
                if arg := self.hook_arg_map.get(ident):
                    dependencies.append(f"{ident} == {arg}")

            constraints.append(Constraint(predicate_desc, dependencies))

        return constraints

    def _collect_path_constraints(self, slicer: Slicer) -> list[Constraint]:
        result = []

        for arg_map, path in zip(self.arg_maps, self.cfg_paths):
            param_deps = [f"{param} == {arg}" for param, arg in arg_map.items()]
            result.append(Constraint("", param_deps))

            for idx, predicate in enumerate(path.predicates):
                dependencies = path.get_predicate_dependencies(idx, slicer, arg_map)
                if not dependencies:
                    print(
                        f"warning: failed to find dependencies of predicate: {predicate.ts_node.text.decode()}",
                        file=sys.stderr,
                    )
                result.append(Constraint(predicate.description(), dependencies))

        return result

    @classmethod
    def _describe_constraints(cls, constraints: list[Constraint]) -> str:
        predicates_s = "\n&& ".join(
            c.predicate_desc for c in constraints if c.predicate_desc
        )

        lines = [cls._markdown_code_block(predicates_s)]

        dep_strs = [
            cls._markdown_code_block("\n".join(c.dependencies))
            for c in constraints
            if c.dependencies
        ]
        lines.extend(["", "where", "", "\n\nand\n\n".join(dep_strs)])

        return "\n".join(lines)

    @staticmethod
    def _markdown_code_block(text: str, language: str = "") -> str:
        return f"```{language}\n{text}\n```"


@cache
def find_predicates(tsnode: TSNode) -> list[Predicate]:
    """Find the predicates that guard tsnode."""

    predicates = []
    parent = tsnode
    child = None
    method_invocation_predicates = []
    while parent.type != "method_declaration":
        child = parent
        #    if child.type == "block":
        #        for c in child.children:
        #            if c.type == "expression_statement":
        #                pass
        #                #all_idts = find_identifiers(c)
        #                #method_name = all_idts[0]
        #                #all_args = get_arguments(c)
        #                #ic(method_name, all_args)
        #   #                 method_invocation_predicates.append(Predicate(c, True, 'method_invocation'))
        parent = parent.parent

        if parent is None:
            break

        assert child is not None

        if parent.type == "if_statement":
            condition = parent.child_by_field_name("condition")
            assert condition is not None
            #  # The predicate is the second child of the if_statement node
            expression = condition.child(1)
            assert expression is not None

            if parent.child_by_field_name("consequence") == child:
                predicates.append(Predicate(expression, True, None, "expr", None))
            else:
                assert parent.child_by_field_name("alternative") == child
                predicates.append(Predicate(expression, False, None, "expr", None))
            # print(parent.text.decode(), '-------')
    predicates = list(reversed(predicates))  # put outer predicate first
    # predicates.extend(method_invocation_predicates)
    return predicates


@cache
def cached_read_file(file: str) -> bytes:
    return Path(file).read_bytes()


@dataclass(eq=True, frozen=True)
class CgEdge:
    caller: str
    callee: str
    position: FilePos


@dataclass(eq=True, frozen=True)
class HookTarget:
    node: CgNode
    position: FilePos
    hookName: str


@dataclass
class CallGraph:
    nodes: dict[str, CgNode]
    edges: list[CgEdge]
    hookTargets: list[HookTarget]

    def merge_unknown_nodes(self) -> CallGraph:
        def key(item: tuple[str, CgNode]) -> int:
            _, node = item
            return self.count_unknowns_in_node(node)

        groups = self.group_nodes_by_equality()

        for group in groups:
            group.sort(key=key)

        nodes = dict(group[0] for group in groups)

        label_map = {}
        for group in groups:
            label, _ = group[0]
            for k, _ in group:
                label_map[k] = label

        for k, v in label_map.items():
            if k != v:
                print("call graph: will merge node", k, "into", v)

        edges = [
            CgEdge(
                caller=label_map[e.caller],
                callee=label_map[e.callee],
                position=e.position,
            )
            for e in self.edges
        ]

        return CallGraph(nodes, edges, self.hookTargets)

    def group_nodes_by_equality(self) -> list[list[tuple[str, CgNode]]]:
        groups = []
        for k, v in self.nodes.items():
            for group in groups:
                _, node = group[0]
                if self.node_equal_with_unknown(v, node):
                    group.append((k, v))
                    break
            else:
                groups.append([(k, v)])
        return groups

    @staticmethod
    def node_equal_with_unknown(n: CgNode, m: CgNode) -> bool:
        UNKNOWN = "<UNKNOWN>"

        def str_eq_with_unknown(s1: str, s2: str) -> bool:
            return UNKNOWN in (s1, s2) or (s1 == s2)

        def list_eq_with_unknown(l1: list[str], l2: list[str]) -> bool:
            unknown_list = [UNKNOWN]

            if l1 != unknown_list and l2 != unknown_list:
                return l1 == l2

            return all(
                str_eq_with_unknown(t1, t2)
                for t1, t2 in zip_longest(n.argTypes, m.argTypes, fillvalue=UNKNOWN)
            )

        return (
            str_eq_with_unknown(n.qualifiedClassName, m.qualifiedClassName)
            and str_eq_with_unknown(n.methodName, m.methodName)
            and list_eq_with_unknown(n.argTypes, m.argTypes)
        )

    @staticmethod
    def count_unknowns_in_node(node: CgNode) -> Any:
        unknown = "<UNKNOWN>"
        return (
            (node.qualifiedClassName == unknown)
            + (node.methodName == unknown)
            + sum(x == unknown for x in node.argTypes)
        )

    def get_arg_map(self, edge: CgEdge) -> dict[str, str]:
        args = []

        tsnode = edge.position.to_tsnode()
        if tsnode is None:
            return {}

        params = self.nodes[edge.caller].argNames

        if len(args) == len(params):
            return dict(zip(params, args))

        print(
            f"warning: failed to find out argument mapping of edge {edge}",
            file=sys.stderr,
        )
        return {}


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


# -m --metadata
# /crs_scratch/experiments/darpa-normaljfuzz-jenkins-id_1_1-TP1-CP1-0-e33f1ef443/meta-data.jso


@click.command()
@click.option(
    "-l",
    "--source-list-file",
    type=click.Path(exists=True),
    required=True,
    help="file that lists source files to analyze, one per line",
)
@click.option("-src", "--harness-source", type=click.Path(), required=True)
@click.option("-d", "--output-dir", type=click.Path(), required=True)
# @click.option("-m", "--meta_data", type=click.Path(), required=True)
@click.option("-s", "--sanitizers", type=str, required=True)
@click.option(
    "-j",
    "--num-processes",
    type=int,
    default=4,
    required=False,
    help="number of parallel joern processes to use",
)
@click.option(
    "-c",
    "--harness-class",
    type=str,
    required=True,
    help="Fully Qualified name of harnesss",
)
def main(
    source_list_file: str | PathLike,
    output_dir: str | PathLike,
    num_processes: int,
    sanitizers: str,
    harness_source: str | PathLike,
    harness_class: str,
) -> None:
    ALLOWED_SANITIZERS = [
        "FileSystemTraversal",
        "ExpressionLanguageInjection",
        "ReflectiveCall",
        "LdapInjection",
        "NamingContextLookup",
        "OsCommandInjection",
        "Deserialization",
        "IntegerOverflow",
        "FileReadWrite",
        "ServerSideRequestForgery",
    ]
    DEFAULT_JAZZER_SANITIZERS = ["IntegerOverflow"]
    sanitizer_list = sanitizers.split(",")
    sanitizer_list = [
        sanitizer for sanitizer in sanitizer_list if sanitizer in ALLOWED_SANITIZERS
    ]

    sanitizer_list = [
        santizer
        for santizer in sanitizer_list
        if santizer not in DEFAULT_JAZZER_SANITIZERS
    ]
    if len(sanitizer_list) == 0:
        print("No sanitizer available for LLM input generation. Exiting.")
        return 0

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    ENTRY = dict(
        qualifiedClassName=harness_class,
        methodName="fuzzerTestOneInput",
        argTypes=["byte[]"],
        argNames=["data"],
    )

    entry = CgNode(**ENTRY)

    PROMPT_HEADER = make_prompt_header(sanitizer_list)

    raw_cg_str = generate_call_graph_str(source_list_file, sanitizers)
    raw_cg = loads_call_graph(raw_cg_str)
    raw_cg_file = Path(output_dir, "raw_cg.json")
    raw_cg_file.write_text(raw_cg_str)

    cg = raw_cg.merge_unknown_nodes()
    # the provional implementation only supports one hook target, multiple prompts can be generated using more targets which can be followed by runtime validation

    icfg_paths = list(
        chain.from_iterable(
            find_icfg_paths(cg, entry, target) for target in cg.hookTargets
        )
    )

    prompts = []

    sources = Path(source_list_file).read_text().splitlines()
    dots_dir = Path('/tmp',f"ddg-dots-{str(randint(1,100000))}")
    dots_dir.mkdir(parents=True,exist_ok=True)
    slicer = Slicer(sources, dots_dir, num_processes)
    # form last path edge
    if len(icfg_paths) == 0:
        print("No paths found in the call graph. Exiting.")
        exit(1)

    selected_path = icfg_paths
    selected_slice = []

    promp_str = ""
    condition_segments = []
    sliced_ts_nodes = []  # a list tsnodes that are sliced from the ddg
    sliced_src_files = set()
    for predicate, arg_map in selected_path:
        # either it is function call or instance method call
        all_names = find_identifiers(predicate.ts_node)
        if len(all_names) == 0:
            return []
        method_name = all_names[0]
        if predicate.type == "method_invocation":
            # to slice the method implementation if line no is -1
            sliced_ts_nodes.append(predicate.ts_node)
            ddg = slicer.slice(predicate.position.file, method_name, -1)
            # try to collect string literals and character literals
        else:
            # to slice the dependencies
            predicate_line_no, _ = predicate.ts_node.start_point
            sliced_ts_nodes.append(predicate.ts_node)
            ddg = slicer.slice(
                predicate.position.file, predicate.scope, predicate_line_no
            )

        line_numbers = set()
        for x in ddg:
            the_type, dep_line_no = CfgPath._parse_ddg_tag(x)
            if the_type in ["METHOD", "PARAM", "METHOD_RETURN"]:
                continue
            line_numbers.add(dep_line_no)
        sliced_src_files.add(predicate.position.file)
        content = cached_read_file(predicate.position.file).decode().splitlines()
        results = [content[line_no] for line_no in line_numbers]
        selected_lines = "\n".join(results)

        code_snippet = f"```\n{selected_lines}\n```"
        hash_val = hashlib.md5(code_snippet.encode()).hexdigest()

        if hash_val not in selected_slice:
            selected_slice.append(hash_val)
            # code_prompt = code_to_markdown(code_snippet)
            promp_str += code_snippet
            arg_map_str = " and ".join(f"{k} == {v}" for k, v in arg_map.items())
            if len(arg_map_str) > 0:
                promp_str += f"\nwhere: {arg_map_str}"
        if predicate.type == "expr":
            condition_segments.append(f"{predicate.description()}")

    print(f"I am preparing some a vocab for you. Please wait a moment.")
    dict_vocab = generate_dict_words(sliced_src_files)
    dict_file_content = []

    for idx, word in enumerate(dict_vocab):
        word = word.strip('"')
        if word:
            copied_word = '"' + "".join(f"\\x{ord(c):02x}" for c in word) + '"'
            dict_file_content.append(f"#{repr(word)}")  # add comments
            dict_file_content.append(f"kw{idx + 1}={copied_word}")

    output_dir.joinpath("dict.txt").write_text("\n".join(dict_file_content))

    condition_pompts = f"Please ensure: \n { ' && '.join(condition_segments) })"
    program_slice_prompts = (
        f"Here are the dataflow slices of the program: \n{promp_str}"
    )

    prompts.append(PROMPT_HEADER)
    prompts.append(condition_pompts)
    prompts.append(program_slice_prompts)
    prompts.append(PROMPT_OUTPUT_REQ)

    prompts_path = output_dir.joinpath("prompts.json")
    prompts_path.write_text(json.dumps(prompts, indent=4))

    harness_code = Path(harness_source).read_text()

    print(f"Dumped generated prompts to {prompts_path}")
    prompt_content = "\n".join(prompts)
    harness_prompt_content = (
        prompt_content
        + f"\nThis is a file that is related with the input data. {harness_code}\n"
    )
    print(prompt_content)
    for idx in range(25):
        bin_data = query_llm_and_run_response(prompt_content)
        if bin_data is None:
            continue
        bin_file_name = output_dir.joinpath(f"{2 * idx}_input.bin")
        bin_file_name.write_bytes(bin_data)

        bin_data = query_llm_and_run_response(harness_prompt_content)
        if bin_data is None:
            continue
        bin_file_name = output_dir.joinpath(f"{2 * idx + 1}_input.bin")
        bin_file_name.write_bytes(bin_data)


def generate_dict_words(filenames: list[str | PathLike]) -> list[str]:
    dict_words = []
    parser = Parser()
    parser.language = JAVA_LANGUAGE
    for filename in filenames:
        with open(filename) as f:
            java_code = f.read()
            dict_words += collect_string_literals(java_code)
    dict_words = [word for word in dict_words if len(word) > 1 and word != '"\n"']
    dict_words = list(set(dict_words))

    return dict_words


def find_icfg_paths(
    cg: CallGraph, entry: CgNode, target: HookTarget
) -> list[Predicate]:
    call_graph_paths = find_call_sequences_to_target(cg, entry, target)

    icfg_paths = []
    cg_adj_matrix = defaultdict(list)
    predicates_on_path = []
    for edge in cg.edges:
        if edge.caller not in cg_adj_matrix:
            cg_adj_matrix[edge.caller] = []
        cg_adj_matrix[edge.caller].append(edge)

    for edges in call_graph_paths:
        cfg_paths = []
        arg_maps = []

        args = []
        method_names_on_path = []
        for edge in edges:
            method_names_on_path.append(cg.nodes[edge.caller].methodName)
        for edge in edges:
            tsnode = edge.position.to_tsnode()
            if tsnode is None:
                print(
                    f"warning: failed to find tsnode for edge {edge}",
                    file=sys.stderr,
                )
                continue

            arg_map = {}
            params = cg.nodes[edge.caller].argNames
            method_name = cg.nodes[edge.caller].methodName
            if len(args) == len(params):
                arg_map = dict(zip(params, args))
            else:
                print(
                    f"warning: failed to find out argument mapping of edge {edge}",
                    file=sys.stderr,
                )
                arg_map = {}
            arg_maps.append(arg_map)

            all_inner_callees = cg_adj_matrix[edge.caller]  # map from caller to edges
            # generate call predicates

            # args = get_arguments(tsnode)
            # check all the call sites in this edge's caller
            line_no, col_no = tsnode.start_point

            e_pos = edge.position
            e_pos.line = line_no
            e_pos.column = col_no

            args = get_arguments(tsnode)
            predicates = find_predicates(tsnode)
            for p in predicates:
                p.position = edge.position
                p.scope = method_name
                predicates_on_path.append((p, {}))

            for ac in all_inner_callees:
                call_node = ac.position.to_tsnode()
                if call_node.type not in ["method_invocation", "expression_statement"]:
                    continue
                all_args = get_arguments(call_node)
                if len(all_args) == 0:
                    continue
                ac_params = cg.nodes[ac.callee].argNames
                if "<UNKNOWN>" in ac_params:
                    continue
                if len(ac_params) != len(all_args):
                    continue
                tmp_arg_map = dict(zip(ac_params, all_args))
                tmp_predicate = Predicate(
                    call_node, True, edge.position, "method_invocation", method_name
                )
                predicates_on_path.append((tmp_predicate, tmp_arg_map))

        assert cg.nodes[edges[-1].callee] == target.node
        params = target.node.argNames
        #        assert len(args) == len(params)
        hook_arg_map = dict(zip(params, args))

        icfg_paths.append(IcfgPath(arg_maps, cfg_paths, target.hookName, hook_arg_map))

    return predicates_on_path


def get_arguments(tsnode: TSNode) -> list[str]:
    if tsnode.type == "method_invocation":
        invocation = tsnode
    else:
        # CtInvocation in Spoon may be an expression statement
        assert tsnode.type == "expression_statement"

        invocation = tsnode.child(0)
        assert invocation

    arg_list = invocation.child_by_field_name("arguments")
    assert arg_list

    args = [arg.text.decode() for arg in arg_list.children]
    exclude = ("(", ")", ",")
    return [arg for arg in args if arg not in exclude]


def generate_call_graph_str(file_list: str | PathLike, sanitizers: str) -> str:
    command = [
        "java",
        "-jar",
        CALL_GRAPH_GENERATOR_JAR,
        "-l",
        str(file_list),
        "-s",
        sanitizers,
    ]
    try:
        print("Trying to generate call graph", " ".join(command))
        cp = subprocess.run(command, capture_output=True, text=True, check=True)
        return cp.stdout
    except subprocess.CalledProcessError as e:
        print("failed to generate call graph:", e.stderr, file=sys.stderr)
        raise


def loads_call_graph(s: str) -> CallGraph:
    cg_data = json.loads(s)
    nodes = {k: CgNode(**v) for k, v in cg_data["nodes"].items()}

    edges = []
    for edge_data in cg_data["edges"]:
        position = FilePos(**edge_data["position"])
        edge = CgEdge(
            caller=edge_data["caller"], callee=edge_data["callee"], position=position
        )
        edges.append(edge)

    hook_targets = []
    for x in cg_data["hookTargets"]:
        node = CgNode(**x["node"])
        position = FilePos(**x["position"])
        hook_targets.append(HookTarget(node, position, x["hookName"]))
    return CallGraph(nodes, edges, hook_targets)


def find_call_sequences_to_target(
    cg: CallGraph, entry: CgNode, target: HookTarget
) -> list[list[CgEdge]]:
    if entry not in cg.nodes.values():
        print(f"{entry} not found in call graph")
        return []

    entry_labels = [k for k, v in cg.nodes.items() if v == entry]
    assert len(entry_labels) == 1, "found multiple entries"
    entry_label = entry_labels[0]

    edges = defaultdict(list)
    for e in cg.edges:
        edges[e.caller].append(e)

    target_labels = [k for k, v in cg.nodes.items() if v == target.node]

    paths = []

    # Each path would be represented as a list[Edge]. nodes_on_path is just used to
    # avoid finding duplicate paths.

    nodes_on_path = deque()
    edges_on_path = deque()

    def dfs(node: str) -> None:
        nodes_on_path.append(node)

        if node in target_labels:
            paths.append(list(edges_on_path))
            return

        for edge in edges[node]:
            if edge.callee not in nodes_on_path:
                edges_on_path.append(edge)

                dfs(edge.callee)

                edges_on_path.pop()

        nodes_on_path.pop()

    # new edges on path = a list of CgNodes
    dfs(entry_label)

    return paths


def formulate_prompt(input_name: str, input_type: str, icfg_desc: str) -> str:
    return (
        f"Give me `{input_name}` of type `{input_type}`, such that the following"
        f" conditions are met:\n\n{icfg_desc}"
        "\n\n"
        "Your answer should be a python program that dumps the expected data to"
        " the file `input.bin`."
    )


def query_llm_and_run_response(prompt: str) -> bytes | None:
    messages = [{"content": prompt, "role": "user"}]
    key = os.getenv("LITELLM_KEY", None)
    response = completion(
        model="gpt-4-0613" if not os.getenv("LITELLM_KEY", None) else "oai-gpt-4o",
        messages=messages,
        base_url=os.getenv("AIXCC_LITELLM_HOSTNAME", None),
        extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        custom_llm_provider="openai",
    )
    content = response.choices[0].message.content
    print(content)
    assert isinstance(content, str)

    try:
        blocks = extract_markdown_code_blocks(content)
        code = blocks[0]
    except Exception:
        return None

    with NamedTemporaryFile(buffering=0, suffix=".py") as f:
        f.write(code.encode())

        with TemporaryDirectory() as tmp_dir:
            cp = subprocess.run(
                ["timeout", "-k", "5s", "10s", "python3", f.name],
                cwd=tmp_dir,
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
            )

            if cp.returncode != 0:
                return None

            bin_path = Path(tmp_dir, "input.bin")
            if not bin_path.is_file():
                return None

            bin = bin_path.read_bytes()

    return bin


def extract_json_code_blocks(content: str) -> str:
    # Extracts JSON code blocks from a markdown string.
    lines = content.splitlines(keepends=True)
    json_blocks = []
    in_json_block = False
    for line in lines:
        if in_json_block:
            json_blocks[-1] += line
            if line.strip() == "```":
                in_json_block = False
        elif line.strip() == "```json":
            json_blocks.append(line)
            in_json_block = True
    return "\n".join(json_blocks)


def code_to_markdown(code_snippet: str) -> str:
    """
    Convert a code snippet to markdown format.

    Parameters:
    code_snippet (str): The code snippet to be converted.

    Returns:
    str: The markdown-formatted code snippet.
    """
    # Markdown formatted code block
    markdown_code = f"```python\n{code_snippet}\n```"
    return markdown_code


def extract_markdown_code_blocks(content: str) -> list[str]:
    lines = content.splitlines(keepends=True)

    in_code_block = False
    start_pattern = r"\s*```\w*\s*"
    end_pattern = r"\s*```\s*"

    start, end = -1, -1
    intervals = []

    for idx, line in enumerate(lines):
        if (not in_code_block) and re.match(start_pattern, line):
            in_code_block = True
            start = idx + 1
        elif in_code_block and re.match(end_pattern, line):
            in_code_block = False
            end = idx
            intervals.append((start, end))

    res = ["".join(lines[start:end]) for start, end in intervals]
    return res


if __name__ == "__main__":
    main()
