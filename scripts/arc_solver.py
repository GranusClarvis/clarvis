#!/usr/bin/env python3
"""ARC-AGI-style pattern completion solver.

Uses rule extraction (symmetry, rotation, color mapping) without LLM.
Each puzzle has training input-output pairs; the solver infers the
transformation and applies it to a test input.
"""

import copy
from typing import List, Tuple, Optional, Callable

Grid = List[List[int]]
Puzzle = dict  # {"train": [{"input": Grid, "output": Grid}], "test": [{"input": Grid}]}


# ── Grid utilities ──────────────────────────────────────────────────

def grid_eq(a: Grid, b: Grid) -> bool:
    if len(a) != len(b):
        return False
    return all(row_a == row_b for row_a, row_b in zip(a, b))


def grid_shape(g: Grid) -> Tuple[int, int]:
    return (len(g), len(g[0]) if g else 0)


def rotate_90(g: Grid) -> Grid:
    """Rotate grid 90° clockwise."""
    rows, cols = grid_shape(g)
    return [[g[rows - 1 - j][i] for j in range(rows)] for i in range(cols)]


def rotate_180(g: Grid) -> Grid:
    return rotate_90(rotate_90(g))


def rotate_270(g: Grid) -> Grid:
    return rotate_90(rotate_90(rotate_90(g)))


def flip_h(g: Grid) -> Grid:
    """Flip horizontally (left-right)."""
    return [row[::-1] for row in g]


def flip_v(g: Grid) -> Grid:
    """Flip vertically (top-bottom)."""
    return g[::-1]


def transpose(g: Grid) -> Grid:
    rows, cols = grid_shape(g)
    return [[g[r][c] for r in range(rows)] for c in range(cols)]


def color_set(g: Grid) -> set:
    return {cell for row in g for cell in row}


def color_counts(g: Grid) -> dict:
    counts = {}
    for row in g:
        for cell in row:
            counts[cell] = counts.get(cell, 0) + 1
    return counts


def apply_color_map(g: Grid, mapping: dict) -> Grid:
    return [[mapping.get(cell, cell) for cell in row] for row in g]


def scale_grid(g: Grid, factor: int) -> Grid:
    """Scale each cell into a factor×factor block."""
    result = []
    for row in g:
        expanded_row = []
        for cell in row:
            expanded_row.extend([cell] * factor)
        for _ in range(factor):
            result.append(list(expanded_row))
    return result


def crop_nonzero(g: Grid) -> Grid:
    """Crop to bounding box of non-zero cells."""
    rows, cols = grid_shape(g)
    min_r, max_r, min_c, max_c = rows, -1, cols, -1
    for r in range(rows):
        for c in range(cols):
            if g[r][c] != 0:
                min_r = min(min_r, r)
                max_r = max(max_r, r)
                min_c = min(min_c, c)
                max_c = max(max_c, c)
    if max_r == -1:
        return g
    return [row[min_c:max_c + 1] for row in g[min_r:max_r + 1]]


def flood_fill(g: Grid, r: int, c: int, target: int, replacement: int) -> Grid:
    """Flood fill from (r,c), replacing target with replacement."""
    g = [row[:] for row in g]
    rows, cols = grid_shape(g)
    if g[r][c] != target or target == replacement:
        return g
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if cr < 0 or cr >= rows or cc < 0 or cc >= cols:
            continue
        if g[cr][cc] != target:
            continue
        g[cr][cc] = replacement
        stack.extend([(cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)])
    return g


def find_enclosed_regions(g: Grid, border_color: int, fill_color: int, bg: int = 0) -> Grid:
    """Fill enclosed background regions bounded by border_color with fill_color."""
    rows, cols = grid_shape(g)
    result = [row[:] for row in g]
    # Mark all bg cells reachable from edges
    visited = [[False] * cols for _ in range(rows)]
    stack = []
    for r in range(rows):
        for c in range(cols):
            if (r == 0 or r == rows - 1 or c == 0 or c == cols - 1) and g[r][c] == bg:
                stack.append((r, c))
    while stack:
        cr, cc = stack.pop()
        if cr < 0 or cr >= rows or cc < 0 or cc >= cols:
            continue
        if visited[cr][cc] or g[cr][cc] != bg:
            continue
        visited[cr][cc] = True
        stack.extend([(cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)])
    # Fill unvisited bg cells
    for r in range(rows):
        for c in range(cols):
            if result[r][c] == bg and not visited[r][c]:
                result[r][c] = fill_color
    return result


# ── Rule extractors ─────────────────────────────────────────────────

def _try_geometric_transforms(train: list) -> Optional[Callable]:
    """Test if output is a geometric transform of input."""
    transforms = [
        ("rotate_90", rotate_90),
        ("rotate_180", rotate_180),
        ("rotate_270", rotate_270),
        ("flip_h", flip_h),
        ("flip_v", flip_v),
        ("transpose", transpose),
    ]
    for name, fn in transforms:
        if all(grid_eq(fn(pair["input"]), pair["output"]) for pair in train):
            return fn
    return None


def _try_color_mapping(train: list) -> Optional[Callable]:
    """Test if output is a color remapping of input (same shape)."""
    if not all(grid_shape(p["input"]) == grid_shape(p["output"]) for p in train):
        return None
    # Build mapping from first pair, verify on rest
    mapping = {}
    for pair in train:
        inp, out = pair["input"], pair["output"]
        for r in range(len(inp)):
            for c in range(len(inp[0])):
                src, dst = inp[r][c], out[r][c]
                if src in mapping:
                    if mapping[src] != dst:
                        return None
                else:
                    mapping[src] = dst
    # Verify mapping is consistent across all pairs
    def apply(g):
        return apply_color_map(g, mapping)
    if all(grid_eq(apply(p["input"]), p["output"]) for p in train):
        return apply
    return None


def _try_scaling(train: list) -> Optional[Callable]:
    """Test if output is a scaled-up version of input."""
    for factor in [2, 3, 4]:
        if all(grid_eq(scale_grid(p["input"], factor), p["output"]) for p in train):
            return lambda g, f=factor: scale_grid(g, f)
    return None


def _try_fill_enclosed(train: list) -> Optional[Callable]:
    """Test if output fills enclosed regions."""
    for pair in train:
        inp, out = pair["input"], pair["output"]
        if grid_shape(inp) != grid_shape(out):
            return None
    # Find which color acts as border and what fill color is used
    # by comparing input and output differences
    first_inp, first_out = train[0]["input"], train[0]["output"]
    rows, cols = grid_shape(first_inp)
    diff_cells = []
    for r in range(rows):
        for c in range(cols):
            if first_inp[r][c] != first_out[r][c]:
                diff_cells.append((r, c, first_inp[r][c], first_out[r][c]))
    if not diff_cells:
        return None
    # All changed cells should go from bg to the same fill color
    bg = diff_cells[0][2]
    fill = diff_cells[0][3]
    if not all(d[2] == bg and d[3] == fill for d in diff_cells):
        return None
    # Determine border color (non-bg, non-fill color in input)
    in_colors = color_set(first_inp) - {bg}
    border_candidates = in_colors - {fill}
    if not border_candidates:
        return None
    border = border_candidates.pop()

    def apply(g):
        return find_enclosed_regions(g, border, fill, bg)

    if all(grid_eq(apply(p["input"]), p["output"]) for p in train):
        return apply
    return None


def _try_crop(train: list) -> Optional[Callable]:
    """Test if output is the cropped non-zero region of input."""
    if all(grid_eq(crop_nonzero(p["input"]), p["output"]) for p in train):
        return crop_nonzero
    return None


def _try_composite(train: list) -> Optional[Callable]:
    """Try combinations: geometric + color map."""
    geo = _try_geometric_transforms(train)
    if geo:
        return geo
    # Try geometric then color
    transforms = [rotate_90, rotate_180, rotate_270, flip_h, flip_v, transpose]
    for tfn in transforms:
        modified_train = [{"input": tfn(p["input"]), "output": p["output"]} for p in train]
        cmap = _try_color_mapping(modified_train)
        if cmap:
            return lambda g, t=tfn, c=cmap: c(t(g))
    return None


# ── Main solver ─────────────────────────────────────────────────────

EXTRACTORS = [
    _try_geometric_transforms,
    _try_color_mapping,
    _try_scaling,
    _try_fill_enclosed,
    _try_crop,
    _try_composite,
]


def solve(puzzle: Puzzle) -> List[Grid]:
    """Solve an ARC-AGI puzzle. Returns predicted outputs for test inputs."""
    train = puzzle["train"]
    test_inputs = [t["input"] for t in puzzle["test"]]

    for extractor in EXTRACTORS:
        transform = extractor(train)
        if transform is not None:
            return [transform(inp) for inp in test_inputs]

    # Fallback: return input unchanged (identity)
    return [copy.deepcopy(inp) for inp in test_inputs]


def evaluate(puzzle: Puzzle) -> dict:
    """Evaluate solver on a puzzle with known test answers."""
    predictions = solve(puzzle)
    results = []
    for i, pred in enumerate(predictions):
        expected = puzzle["test"][i].get("output")
        if expected is None:
            results.append({"index": i, "correct": None, "reason": "no expected output"})
        else:
            correct = grid_eq(pred, expected)
            results.append({"index": i, "correct": correct})
    return {
        "predictions": predictions,
        "results": results,
        "score": sum(1 for r in results if r.get("correct")) / max(len(results), 1),
    }


# ── Puzzle bank ─────────────────────────────────────────────────────

PUZZLES = {
    "color_swap": {
        "description": "Swap color 1↔2, keep 0 unchanged",
        "train": [
            {"input": [[0, 1, 0], [1, 2, 1], [0, 1, 0]],
             "output": [[0, 2, 0], [2, 1, 2], [0, 2, 0]]},
            {"input": [[1, 1, 2], [0, 2, 0], [2, 1, 1]],
             "output": [[2, 2, 1], [0, 1, 0], [1, 2, 2]]},
        ],
        "test": [
            {"input": [[1, 0, 2], [0, 0, 0], [2, 0, 1]],
             "output": [[2, 0, 1], [0, 0, 0], [1, 0, 2]]},
        ],
    },
    "rotate_90": {
        "description": "Rotate grid 90° clockwise",
        "train": [
            {"input": [[1, 2], [3, 4]],
             "output": [[3, 1], [4, 2]]},
            {"input": [[5, 6, 7], [8, 9, 0]],
             "output": [[8, 5], [9, 6], [0, 7]]},
        ],
        "test": [
            {"input": [[1, 0, 0], [0, 2, 0], [0, 0, 3]],
             "output": [[0, 0, 1], [0, 2, 0], [3, 0, 0]]},
        ],
    },
    "flip_horizontal": {
        "description": "Mirror grid left-right",
        "train": [
            {"input": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
             "output": [[0, 0, 1], [0, 1, 0], [1, 0, 0]]},
            {"input": [[3, 0, 0, 0], [0, 3, 0, 0]],
             "output": [[0, 0, 0, 3], [0, 0, 3, 0]]},
        ],
        "test": [
            {"input": [[2, 5, 0], [0, 5, 2], [2, 0, 0]],
             "output": [[0, 5, 2], [2, 5, 0], [0, 0, 2]]},
        ],
    },
    "fill_enclosed": {
        "description": "Fill enclosed background (0) regions with color 3, borders are color 1",
        "train": [
            {"input": [[0, 0, 0, 0, 0],
                        [0, 1, 1, 1, 0],
                        [0, 1, 0, 1, 0],
                        [0, 1, 1, 1, 0],
                        [0, 0, 0, 0, 0]],
             "output": [[0, 0, 0, 0, 0],
                         [0, 1, 1, 1, 0],
                         [0, 1, 3, 1, 0],
                         [0, 1, 1, 1, 0],
                         [0, 0, 0, 0, 0]]},
            {"input": [[1, 1, 1, 0],
                        [1, 0, 1, 0],
                        [1, 0, 1, 0],
                        [1, 1, 1, 0]],
             "output": [[1, 1, 1, 0],
                         [1, 3, 1, 0],
                         [1, 3, 1, 0],
                         [1, 1, 1, 0]]},
        ],
        "test": [
            {"input": [[0, 0, 0, 0, 0, 0],
                        [0, 1, 1, 1, 1, 0],
                        [0, 1, 0, 0, 1, 0],
                        [0, 1, 0, 0, 1, 0],
                        [0, 1, 1, 1, 1, 0],
                        [0, 0, 0, 0, 0, 0]],
             "output": [[0, 0, 0, 0, 0, 0],
                         [0, 1, 1, 1, 1, 0],
                         [0, 1, 3, 3, 1, 0],
                         [0, 1, 3, 3, 1, 0],
                         [0, 1, 1, 1, 1, 0],
                         [0, 0, 0, 0, 0, 0]]},
        ],
    },
    "scale_2x": {
        "description": "Scale each cell to a 2×2 block",
        "train": [
            {"input": [[1, 2], [3, 0]],
             "output": [[1, 1, 2, 2],
                         [1, 1, 2, 2],
                         [3, 3, 0, 0],
                         [3, 3, 0, 0]]},
            {"input": [[5]],
             "output": [[5, 5], [5, 5]]},
        ],
        "test": [
            {"input": [[4, 0, 1], [0, 7, 0]],
             "output": [[4, 4, 0, 0, 1, 1],
                         [4, 4, 0, 0, 1, 1],
                         [0, 0, 7, 7, 0, 0],
                         [0, 0, 7, 7, 0, 0]]},
        ],
    },
}


def run_all() -> dict:
    """Run solver on all built-in puzzles. Returns summary."""
    total, correct = 0, 0
    details = {}
    for name, puzzle in PUZZLES.items():
        result = evaluate(puzzle)
        total += len(result["results"])
        correct += sum(1 for r in result["results"] if r.get("correct"))
        details[name] = result["score"]
        status = "PASS" if result["score"] == 1.0 else "FAIL"
        print(f"  {name}: {status} (score={result['score']:.2f})")
    overall = correct / total if total else 0
    print(f"\nOverall: {correct}/{total} correct ({overall:.0%})")
    return {"total": total, "correct": correct, "accuracy": overall, "details": details}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "bench":
        print("ARC-AGI Solver Benchmark")
        print("=" * 40)
        run_all()
    else:
        print("ARC-AGI Pattern Solver")
        print("Usage: arc_solver.py bench")
        print(f"Puzzles: {len(PUZZLES)}")
        print(f"Rules: geometric transforms, color mapping, scaling, fill enclosed, crop")
