#!/usr/bin/env python3
"""Audit a graphify knowledge graph against this repository's actual imports.

graphify resolves symbols by bare name with no module-origin check. On this
codebase that produces two opposite errors:

  Defect A - under-linking. Calls reached through an aliased local module
      import pwb_toolbox.performance as pwb_perf
      pwb_perf.sharpe_ratio(nav)
    bind at runtime but are never emitted as edges, because the resolver
    handles `from X import name` and not `alias.attr`.

  Defect B - over-linking. A name imported from a third-party package that
    collides with a same-named symbol defined in this repo
      from datasets import load_dataset      # HuggingFace
      pwb_toolbox/datasets/__init__.py:664   def load_dataset(...)
    is matched to the local definition, inventing a cross-module edge.

Both distort betweenness far more than degree: a single fake edge is a
shortcut across the whole graph, while degree barely moves. Re-run this after
`graphify update` to re-measure drift.

Usage:
    python tools/graph_audit.py
    python tools/graph_audit.py --graph graphify-out/graph.json --root .
    python tools/graph_audit.py --json          # machine-readable summary

Exit status is 0 unless --strict is passed, in which case any finding exits 1.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

# Top-level packages that belong to this repository. Anything else in an
# absolute `from X import ...` is third-party or stdlib.
LOCAL_PKGS = {"pwb_toolbox", "pwb_toolbox_legacy", "tools"}

SKIP_DIRS = {"graphify-out", ".venv", ".git", "__pycache__", "build", "dist"}


# --------------------------------------------------------------------- graph


class Graph:
    """Read-only view of graphify-out/graph.json."""

    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.raw = data
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.links = data["links"]

        self.by_file: dict[str, list[str]] = defaultdict(list)
        self.by_file_label: dict[tuple[str, str], str] = {}
        self.by_label: dict[str, list[tuple[str, str]]] = defaultdict(list)

        for nid, n in self.nodes.items():
            src = n.get("source_file")
            if not src:
                continue
            label = self._norm(n.get("label"))
            self.by_file[src].append(nid)
            self.by_file_label[(src, label)] = nid
            self.by_label[label].append((src, nid))

        self.pairs = {frozenset((e["source"], e["target"])) for e in self.links}

    @staticmethod
    def _norm(label: str | None) -> str:
        return (label or "").replace("()", "").lstrip(".").strip()

    def linked(self, target: str, caller_file: str) -> bool:
        """True if any node in caller_file already touches target."""
        return any(frozenset((target, c)) in self.pairs for c in self.by_file[caller_file])

    def inferred_count(self) -> int:
        return sum(1 for e in self.links if e.get("confidence") == "INFERRED")


# ------------------------------------------------------------------ scanning


def iter_py_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        if SKIP_DIRS & set(p.parts):
            continue
        yield p


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_def(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    """Name of the nearest enclosing function/class, or None at module level."""
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return cur.name
        cur = parents.get(cur)
    return None


class Resolver:
    """Maps a dotted local module + attribute onto a graph node."""

    def __init__(self, root: Path, graph: Graph):
        self.root = root
        self.graph = graph

    def rel(self, p: Path) -> str:
        return str(p.resolve().relative_to(self.root))

    def module_files(self, mod: str) -> list[str]:
        parts = mod.split(".")
        out = []
        pkg = self.root.joinpath(*parts, "__init__.py")
        submod = self.root.joinpath(*parts[:-1], parts[-1] + ".py")
        if pkg.exists():
            out.append(self.rel(pkg))
        if submod.exists():
            out.append(self.rel(submod))
        return out

    def resolve(self, mod: str, attr: str) -> tuple[str | None, str | None]:
        """Find the node for `mod.attr`, following package re-exports.

        `pwb_toolbox/performance/__init__.py` re-exports from `metrics.py`, so a
        direct (file, label) hit on the __init__ usually misses; fall back to
        searching the package subtree and prefer the real definition site.
        """
        for f in self.module_files(mod):
            nid = self.graph.by_file_label.get((f, attr))
            if nid:
                return nid, f

        pkg_dir = self.root.joinpath(*mod.split("."))
        if pkg_dir.is_dir():
            prefix = self.rel(pkg_dir) + "/"
            hits = [(f, nid) for (f, nid) in self.graph.by_label.get(attr, [])
                    if f.startswith(prefix)]
            for f, nid in hits:
                if not f.endswith("__init__.py"):
                    return nid, f
            if hits:
                return hits[0][1], hits[0][0]
        return None, None


def scan(root: Path, graph: Graph):
    """Return (defect_a, defect_b) finding lists."""
    resolver = Resolver(root, graph)

    # Every top-level def/class in the repo, for collision detection.
    repo_defs: dict[str, set[str]] = defaultdict(set)
    parsed = {}
    for p in iter_py_files(root):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        r = resolver.rel(p)
        parsed[r] = (p, tree)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                repo_defs[node.name].add(r)

    defect_a, defect_b = [], []

    for r, (p, tree) in parsed.items():
        parents = parent_map(tree)
        pdir = p.parent

        alias_map: dict[str, str] = {}   # alias -> local dotted module
        third: dict[str, str] = {}       # bound name -> third-party package

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname and a.name.split(".")[0] in LOCAL_PKGS:
                        alias_map[a.asname] = a.name
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue                        # explicit relative -> local
                mod = node.module or ""
                top = mod.split(".")[0]
                if not mod or top in LOCAL_PKGS:
                    continue
                # A same-directory sibling module is a local implicit-relative
                # import, not third-party. Missing this check reports false
                # collisions (e.g. `from ssrn_abstract import SsrnAbstract`).
                if (pdir / f"{top}.py").exists() or (pdir / top / "__init__.py").exists():
                    continue
                for a in node.names:
                    third[a.asname or a.name] = mod

        for node in ast.walk(tree):
            # Defect A: alias.attr(...)
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in alias_map):
                mod = alias_map[node.func.value.id]
                tgt, tgt_file = resolver.resolve(mod, node.func.attr)
                if not tgt:
                    continue                        # callee absent from graph
                if graph.linked(tgt, r):
                    continue                        # edge already present
                scope = enclosing_def(node, parents)
                caller = graph.by_file_label.get((r, scope)) if scope else None
                defect_a.append({
                    "caller_file": r,
                    "line": node.lineno,
                    "alias": node.func.value.id,
                    "attr": node.func.attr,
                    "module": mod,
                    "target_file": tgt_file,
                    "target_node": tgt,
                    "caller_node": caller or graph.by_file_label.get((r, Path(r).name)),
                })

            # Defect B: any load of a third-party name shadowed by a repo symbol
            elif (isinstance(node, ast.Name)
                  and isinstance(node.ctx, ast.Load)
                  and node.id in third):
                for local_file in repo_defs.get(node.id, ()):
                    if local_file == r:
                        continue
                    tgt = graph.by_file_label.get((local_file, node.id))
                    if tgt and graph.linked(tgt, r):
                        defect_b.append({
                            "caller_file": r,
                            "line": node.lineno,
                            "package": third[node.id],
                            "name": node.id,
                            "shadowed_by": local_file,
                            "target_node": tgt,
                        })

    return defect_a, defect_b


# ----------------------------------------------------------------- reporting


def fake_edges(graph: Graph, defect_b) -> set[frozenset]:
    out = set()
    for f in defect_b:
        for c in graph.by_file[f["caller_file"]]:
            pair = frozenset((f["target_node"], c))
            if pair in graph.pairs:
                out.add(pair)
    return out


def centrality_impact(graph: Graph, defect_a, defect_b):
    """Recompute betweenness on the corrected graph. Needs networkx."""
    try:
        import networkx as nx
    except ImportError:
        return None

    before = nx.Graph()
    before.add_nodes_from(graph.nodes)
    for e in graph.links:
        before.add_edge(e["source"], e["target"])

    after = before.copy()
    for f in defect_a:
        if f["caller_node"] and f["target_node"]:
            after.add_edge(f["caller_node"], f["target_node"])
    for pair in fake_edges(graph, defect_b):
        a, b = tuple(pair)
        if after.has_edge(a, b):
            after.remove_edge(a, b)

    b0 = nx.betweenness_centrality(before)
    b1 = nx.betweenness_centrality(after)
    touched = {f["target_node"] for f in defect_a} | {f["target_node"] for f in defect_b}
    rows = []
    for nid in touched:
        rows.append((graph.nodes[nid].get("label", nid), b0.get(nid, 0.0), b1.get(nid, 0.0)))
    rows.sort(key=lambda r: -abs(r[2] - r[1]))
    return {
        "edges_before": before.number_of_edges(),
        "edges_after": after.number_of_edges(),
        "rows": rows,
        "top_after": sorted(
            ((graph.nodes[n].get("label", n), v) for n, v in b1.items()),
            key=lambda r: -r[1],
        )[:5],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", default="graphify-out/graph.json")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true", help="emit a JSON summary only")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    gpath = Path(args.graph)
    if not gpath.exists():
        print(f"error: no graph at {gpath}. Run `/graphify .` first.", file=sys.stderr)
        return 2

    graph = Graph(gpath)
    defect_a, defect_b = scan(root, graph)
    fakes = fake_edges(graph, defect_b)
    total = len(graph.links)
    inferred = graph.inferred_count()

    if args.json:
        print(json.dumps({
            "edges": total,
            "inferred": inferred,
            "defect_a_missing_edges": len(defect_a),
            "defect_b_fake_edges": len(fakes),
            "defect_b_sites": len(defect_b),
            "corrected_edges": total - len(fakes) + len(defect_a),
            "defect_a": defect_a,
            "defect_b": defect_b,
        }, indent=2))
        return 1 if (args.strict and (defect_a or defect_b)) else 0

    print("=" * 74)
    print("DEFECT A - under-linking (calls via aliased local module imports)")
    print("=" * 74)
    print(f"missing edges: {len(defect_a)}\n")
    grouped = defaultdict(list)
    for f in defect_a:
        grouped[f["caller_file"]].append(f)
    for caller in sorted(grouped):
        print(f"  {caller}")
        for f in sorted(grouped[caller], key=lambda x: x["line"]):
            print(f"    :{f['line']:<5} {f['alias']}.{f['attr']}()  ->  {f['target_file']}")

    print()
    print("=" * 74)
    print("DEFECT B - over-linking (third-party name shadowed by a repo symbol)")
    print("=" * 74)
    print(f"colliding sites: {len(defect_b)}   distinct fake edges: {len(fakes)}\n")
    agg = defaultdict(lambda: [0, set()])
    for f in defect_b:
        key = (f["package"], f["name"], f["shadowed_by"])
        agg[key][0] += 1
        agg[key][1].add(f["caller_file"])
    for (pkg, name, shadow), (count, files) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        print(f"  `from {pkg} import {name}`  shadowed by  {shadow}")
        print(f"    {count} sites / {len(files)} files")
        for f in sorted(files):
            print(f"      {f}")
        print()

    print("=" * 74)
    print("IMPACT")
    print("=" * 74)
    pct = lambda n: f"{100 * n / total:.2f}%" if total else "n/a"
    print(f"  edges in graph        : {total}  (INFERRED: {inferred}, {pct(inferred)})")
    print(f"  fake edges present    : {len(fakes)}  ({pct(len(fakes))})")
    print(f"  real edges missing    : {len(defect_a)}  ({pct(len(defect_a))})")
    print(f"  corrected edge count  : {total - len(fakes) + len(defect_a)}")
    print(f"  total error surface   : {len(fakes) + len(defect_a)}  ({pct(len(fakes) + len(defect_a))})")

    impact = centrality_impact(graph, defect_a, defect_b)
    if impact is None:
        print("\n  (install networkx for the betweenness impact section)")
    else:
        print()
        print("=" * 74)
        print("BETWEENNESS - affected nodes, before -> after correction")
        print("=" * 74)
        for label, b0, b1 in impact["rows"][:10]:
            delta = 100 * (b1 - b0) / b0 if b0 else 0.0
            print(f"  {label[:40]:<42}{b0:.4f} -> {b1:.4f}  ({delta:+.0f}%)")
        print("\n  corrected top bridges:")
        for label, v in impact["top_after"]:
            print(f"    {v:.4f}  {label}")

    return 1 if (args.strict and (defect_a or defect_b)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
