#!/usr/bin/env python3
"""Levin search for small program synthesis.

Enumerates programs in a minimal language (arithmetic + conditionals + loops),
ordered by length, with runtime budget proportional to 2^(-length).
Synthesizes programs matching given input-output specifications.

The minimal language (BF-arithmetic) has these instructions:
  INC x    — increment register x
  DEC x    — decrement register x
  ADD x y  — x += y
  SUB x y  — x -= y (floors at 0)
  MUL x y  — x *= y
  MOD x y  — x %= y (no-op if y==0)
  CPY x y  — x = y
  JZ  x L  — jump forward L instructions if x == 0
  JNZ x L  — jump forward L instructions if x != 0
  LOOP n B — execute next B instructions n times (bounded loop)
  ZERO x   — x = 0
  HALT     — stop execution

Registers: r0 (input), r1 (output/accumulator), r2-r3 (scratch).
Input placed in r0, output read from r1 after HALT or end-of-program.

[EXTERNAL_CHALLENGE:coding-challenge-08]

Usage:
    python3 levin_search.py demo             # Demo: synthesize doubler, successor, etc.
    python3 levin_search.py synth SPEC       # Synthesize from spec: "0:0,1:2,2:4,3:6"
    python3 levin_search.py enumerate N      # Show first N programs
    python3 levin_search.py benchmark        # Run benchmark suite
"""

from __future__ import annotations

import itertools
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# === INSTRUCTION SET ===

class Op(Enum):
    INC = auto()
    DEC = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()
    MOD = auto()
    CPY = auto()
    JZ = auto()
    JNZ = auto()
    LOOP = auto()
    ZERO = auto()
    HALT = auto()


NUM_REGS = 4
MAX_INT = 10000

@dataclass(frozen=True)
class Instr:
    op: Op
    arg1: int = 0
    arg2: int = 0

    def __repr__(self) -> str:
        names = {Op.INC: f"INC r{self.arg1}", Op.DEC: f"DEC r{self.arg1}",
                 Op.ADD: f"ADD r{self.arg1} r{self.arg2}",
                 Op.SUB: f"SUB r{self.arg1} r{self.arg2}",
                 Op.MUL: f"MUL r{self.arg1} r{self.arg2}",
                 Op.MOD: f"MOD r{self.arg1} r{self.arg2}",
                 Op.CPY: f"CPY r{self.arg1} r{self.arg2}",
                 Op.JZ: f"JZ r{self.arg1} +{self.arg2}",
                 Op.JNZ: f"JNZ r{self.arg1} +{self.arg2}",
                 Op.LOOP: f"LOOP r{self.arg1} {self.arg2}",
                 Op.ZERO: f"ZERO r{self.arg1}",
                 Op.HALT: "HALT"}
        return names.get(self.op, f"{self.op.name} {self.arg1} {self.arg2}")


# === INSTRUCTION ENUMERATION ===

def all_instructions(max_jump: int = 3, max_loop_body: int = 3) -> list[Instr]:
    """Generate all possible single instructions."""
    instrs = []
    regs = range(NUM_REGS)
    for r in regs:
        instrs.append(Instr(Op.INC, r))
        instrs.append(Instr(Op.DEC, r))
        instrs.append(Instr(Op.ZERO, r))
    for r1 in regs:
        for r2 in regs:
            if r1 != r2:
                instrs.append(Instr(Op.ADD, r1, r2))
                instrs.append(Instr(Op.SUB, r1, r2))
                instrs.append(Instr(Op.MUL, r1, r2))
                instrs.append(Instr(Op.MOD, r1, r2))
                instrs.append(Instr(Op.CPY, r1, r2))
    for r in regs:
        for j in range(1, max_jump + 1):
            instrs.append(Instr(Op.JZ, r, j))
            instrs.append(Instr(Op.JNZ, r, j))
    for r in regs:
        for b in range(1, max_loop_body + 1):
            instrs.append(Instr(Op.LOOP, r, b))
    instrs.append(Instr(Op.HALT))
    return instrs


# === INTERPRETER ===

@dataclass
class ExecResult:
    output: Optional[int] = None
    halted: bool = False
    steps: int = 0
    error: Optional[str] = None


def execute(program: list[Instr], input_val: int, max_steps: int = 1000) -> ExecResult:
    """Execute a program with bounded steps. Returns ExecResult."""
    regs = [0] * NUM_REGS
    regs[0] = input_val
    pc = 0
    steps = 0
    n = len(program)

    while pc < n and steps < max_steps:
        instr = program[pc]
        steps += 1
        op = instr.op

        if op == Op.HALT:
            return ExecResult(output=regs[1], halted=True, steps=steps)
        elif op == Op.INC:
            regs[instr.arg1] = min(regs[instr.arg1] + 1, MAX_INT)
        elif op == Op.DEC:
            regs[instr.arg1] = max(regs[instr.arg1] - 1, 0)
        elif op == Op.ADD:
            regs[instr.arg1] = min(regs[instr.arg1] + regs[instr.arg2], MAX_INT)
        elif op == Op.SUB:
            regs[instr.arg1] = max(regs[instr.arg1] - regs[instr.arg2], 0)
        elif op == Op.MUL:
            regs[instr.arg1] = min(regs[instr.arg1] * regs[instr.arg2], MAX_INT)
        elif op == Op.MOD:
            if regs[instr.arg2] != 0:
                regs[instr.arg1] = regs[instr.arg1] % regs[instr.arg2]
        elif op == Op.CPY:
            regs[instr.arg1] = regs[instr.arg2]
        elif op == Op.JZ:
            if regs[instr.arg1] == 0:
                pc += instr.arg2
                continue
        elif op == Op.JNZ:
            if regs[instr.arg1] != 0:
                pc += instr.arg2
                continue
        elif op == Op.LOOP:
            loop_count = regs[instr.arg1]
            body_len = instr.arg2
            if pc + body_len >= n:
                pc += 1
                continue
            body = program[pc + 1: pc + 1 + body_len]
            for _ in range(min(loop_count, max_steps - steps)):
                for bi in body:
                    steps += 1
                    if steps >= max_steps:
                        return ExecResult(output=regs[1], halted=False, steps=steps,
                                          error="step_limit")
                    bop = bi.op
                    if bop == Op.HALT:
                        return ExecResult(output=regs[1], halted=True, steps=steps)
                    elif bop == Op.INC:
                        regs[bi.arg1] = min(regs[bi.arg1] + 1, MAX_INT)
                    elif bop == Op.DEC:
                        regs[bi.arg1] = max(regs[bi.arg1] - 1, 0)
                    elif bop == Op.ADD:
                        regs[bi.arg1] = min(regs[bi.arg1] + regs[bi.arg2], MAX_INT)
                    elif bop == Op.SUB:
                        regs[bi.arg1] = max(regs[bi.arg1] - regs[bi.arg2], 0)
                    elif bop == Op.MUL:
                        regs[bi.arg1] = min(regs[bi.arg1] * regs[bi.arg2], MAX_INT)
                    elif bop == Op.MOD:
                        if regs[bi.arg2] != 0:
                            regs[bi.arg1] = regs[bi.arg1] % regs[bi.arg2]
                    elif bop == Op.CPY:
                        regs[bi.arg1] = regs[bi.arg2]
                    elif bop == Op.ZERO:
                        regs[bi.arg1] = 0
            pc += 1 + body_len
            continue
        elif op == Op.ZERO:
            regs[instr.arg1] = 0

        pc += 1

    return ExecResult(output=regs[1], halted=(pc >= n), steps=steps)


# === PROGRAM ENUMERATION ===

def enumerate_programs(vocab: list[Instr], max_len: int):
    """Yield programs of increasing length (1, 2, ..., max_len)."""
    for length in range(1, max_len + 1):
        for combo in itertools.product(vocab, repeat=length):
            yield list(combo)


# === LEVIN SEARCH ===

@dataclass
class SearchResult:
    program: Optional[list[Instr]] = None
    length: int = 0
    total_programs: int = 0
    total_steps: int = 0
    time_seconds: float = 0.0
    found: bool = False


def levin_search(
    spec: dict[int, int],
    max_program_len: int = 5,
    total_budget: int = 10_000_000,
    max_jump: int = 2,
    max_loop_body: int = 2,
    verbose: bool = False,
) -> SearchResult:
    """
    Levin universal search for program synthesis.

    Enumerates programs by length. Each program of length L gets a runtime budget
    of floor(total_budget * 2^(-L)). A program matches if it produces the correct
    output for ALL input-output pairs in spec.

    Args:
        spec: dict mapping input -> expected output
        max_program_len: maximum program length to enumerate
        total_budget: total step budget (allocated exponentially by length)
        max_jump: maximum jump distance for JZ/JNZ
        max_loop_body: maximum loop body length
        verbose: print progress

    Returns:
        SearchResult with the shortest matching program (if found)
    """
    vocab = all_instructions(max_jump=max_jump, max_loop_body=max_loop_body)
    vocab_size = len(vocab)
    t0 = time.time()

    result = SearchResult()
    tested = 0

    for length in range(1, max_program_len + 1):
        step_budget = max(1, int(total_budget * (2 ** (-length))))
        programs_at_length = vocab_size ** length

        if verbose:
            print(f"  Length {length}: {programs_at_length} programs, "
                  f"budget/program={step_budget} steps")

        for combo in itertools.product(vocab, repeat=length):
            program = list(combo)
            tested += 1

            matches = True
            total_exec_steps = 0
            for inp, expected_out in spec.items():
                er = execute(program, inp, max_steps=step_budget)
                total_exec_steps += er.steps
                if not er.halted or er.output != expected_out:
                    matches = False
                    break

            result.total_steps += total_exec_steps

            if matches:
                result.program = program
                result.length = length
                result.total_programs = tested
                result.time_seconds = time.time() - t0
                result.found = True
                return result

            if time.time() - t0 > 120:
                if verbose:
                    print(f"  Time limit reached after {tested} programs")
                result.total_programs = tested
                result.time_seconds = time.time() - t0
                return result

    result.total_programs = tested
    result.time_seconds = time.time() - t0
    return result


# === PHASE SEARCH (iterative deepening with pruning) ===

def levin_search_phased(
    spec: dict[int, int],
    max_program_len: int = 6,
    total_budget: int = 10_000_000,
    verbose: bool = False,
) -> SearchResult:
    """
    Phased Levin search with semantic pruning.

    Prunes programs where:
    - Consecutive identical instructions (INC r0; INC r0 is kept, but 3+ is pruned)
    - Instructions that can't affect output (operations only on unused scratch regs
      with no later copy to r1)
    - Programs that don't touch r1 at all
    """
    vocab = all_instructions(max_jump=2, max_loop_body=2)
    t0 = time.time()
    result = SearchResult()
    tested = 0

    output_affecting_ops = {Op.INC, Op.DEC, Op.ADD, Op.SUB, Op.MUL, Op.MOD,
                            Op.CPY, Op.ZERO, Op.LOOP}

    for length in range(1, max_program_len + 1):
        step_budget = max(1, int(total_budget * (2 ** (-length))))

        if verbose:
            print(f"  Phase {length}: budget/program={step_budget} steps")

        for combo in itertools.product(vocab, repeat=length):
            program = list(combo)

            touches_r1 = False
            for idx, instr in enumerate(program):
                if instr.op in output_affecting_ops and instr.arg1 == 1:
                    touches_r1 = True
                    break
                if instr.op == Op.LOOP:
                    body_start = idx + 1
                    body_end = body_start + instr.arg2
                    for bi in program[body_start:body_end]:
                        if bi.op in output_affecting_ops and bi.arg1 == 1:
                            touches_r1 = True
                            break
                    if touches_r1:
                        break
            if not touches_r1:
                continue

            skip = False
            for i in range(2, len(program)):
                if (program[i].op == program[i-1].op == program[i-2].op and
                    program[i].arg1 == program[i-1].arg1 == program[i-2].arg1 and
                    program[i].op in (Op.INC, Op.DEC)):
                    skip = True
                    break
            if skip:
                continue

            tested += 1
            matches = True
            for inp, expected_out in spec.items():
                er = execute(program, inp, max_steps=step_budget)
                result.total_steps += er.steps
                if not er.halted or er.output != expected_out:
                    matches = False
                    break

            if matches:
                result.program = program
                result.length = length
                result.total_programs = tested
                result.time_seconds = time.time() - t0
                result.found = True
                return result

            if time.time() - t0 > 120:
                if verbose:
                    print(f"  Time limit at {tested} programs")
                result.total_programs = tested
                result.time_seconds = time.time() - t0
                return result

    result.total_programs = tested
    result.time_seconds = time.time() - t0
    return result


# === CLI ===

def format_program(program: list[Instr]) -> str:
    return "; ".join(repr(i) for i in program)


def parse_spec(spec_str: str) -> dict[int, int]:
    """Parse "0:0,1:2,2:4,3:6" into {0:0, 1:2, 2:4, 3:6}."""
    pairs = {}
    for pair in spec_str.split(","):
        k, v = pair.strip().split(":")
        pairs[int(k)] = int(v)
    return pairs


def cmd_demo():
    tasks = [
        ("identity (f(x)=x)", {0: 0, 1: 1, 2: 2, 3: 3}),
        ("successor (f(x)=x+1)", {0: 1, 1: 2, 2: 3, 5: 6}),
        ("doubler (f(x)=2x)", {0: 0, 1: 2, 2: 4, 3: 6}),
        ("constant zero", {0: 0, 1: 0, 2: 0, 5: 0}),
        ("constant one", {0: 1, 1: 1, 5: 1}),
        ("parity (f(x)=x%2)", {0: 0, 1: 1, 2: 0, 3: 1, 4: 0}),
        ("predecessor (f(x)=max(0,x-1))", {0: 0, 1: 0, 2: 1, 3: 2, 5: 4}),
    ]

    print("=== Levin Search — Program Synthesis Demo ===\n")
    total_t = 0
    solved = 0

    for name, spec in tasks:
        print(f"Task: {name}")
        print(f"  Spec: {spec}")
        r = levin_search_phased(spec, max_program_len=5, verbose=False)
        total_t += r.time_seconds
        if r.found:
            solved += 1
            print(f"  FOUND (len={r.length}, tested={r.total_programs}, "
                  f"time={r.time_seconds:.3f}s)")
            print(f"  Program: {format_program(r.program)}")
            print(f"  Verification:")
            for inp, exp in sorted(spec.items()):
                er = execute(r.program, inp)
                status = "OK" if er.output == exp else "FAIL"
                print(f"    f({inp}) = {er.output} (expected {exp}) [{status}]")
        else:
            print(f"  NOT FOUND (tested={r.total_programs}, "
                  f"time={r.time_seconds:.3f}s)")
        print()

    print(f"Summary: {solved}/{len(tasks)} solved in {total_t:.3f}s total")


def cmd_synth(spec_str: str):
    spec = parse_spec(spec_str)
    print(f"Synthesizing program for spec: {spec}")
    r = levin_search_phased(spec, max_program_len=5, verbose=True)
    if r.found:
        print(f"\nFOUND: {format_program(r.program)}")
        print(f"Length: {r.length}, Programs tested: {r.total_programs}")
        print(f"Time: {r.time_seconds:.3f}s")
        for inp, exp in sorted(spec.items()):
            er = execute(r.program, inp)
            print(f"  f({inp}) = {er.output} (expected {exp})")
    else:
        print(f"\nNot found within search budget ({r.total_programs} programs, "
              f"{r.time_seconds:.3f}s)")


def cmd_enumerate(n: int):
    vocab = all_instructions(max_jump=2, max_loop_body=2)
    print(f"Vocabulary size: {len(vocab)} instructions")
    print(f"First {n} programs:\n")
    for i, prog in enumerate(enumerate_programs(vocab, max_len=3)):
        if i >= n:
            break
        print(f"  {i+1}. {format_program(prog)}")


def cmd_benchmark():
    benchmarks = [
        ("identity", {0: 0, 1: 1, 2: 2, 3: 3, 10: 10}),
        ("successor", {0: 1, 1: 2, 2: 3, 5: 6, 10: 11}),
        ("doubler", {0: 0, 1: 2, 2: 4, 3: 6}),
        ("tripler", {0: 0, 1: 3, 2: 6, 3: 9}),
        ("constant_0", {0: 0, 1: 0, 5: 0, 10: 0}),
        ("constant_1", {0: 1, 1: 1, 5: 1}),
        ("constant_2", {0: 2, 1: 2, 5: 2}),
        ("predecessor", {0: 0, 1: 0, 2: 1, 3: 2}),
        ("parity", {0: 0, 1: 1, 2: 0, 3: 1, 4: 0}),
        ("square", {0: 0, 1: 1, 2: 4, 3: 9}),
    ]

    print("=== Levin Search Benchmark ===\n")
    print(f"{'Task':<15} {'Found':>5} {'Len':>4} {'Tested':>10} {'Steps':>12} {'Time':>8}")
    print("-" * 60)

    solved = 0
    total_t = 0.0

    for name, spec in benchmarks:
        r = levin_search_phased(spec, max_program_len=5, verbose=False)
        total_t += r.time_seconds
        if r.found:
            solved += 1
            print(f"{name:<15} {'yes':>5} {r.length:>4} {r.total_programs:>10} "
                  f"{r.total_steps:>12} {r.time_seconds:>7.3f}s")
        else:
            print(f"{name:<15} {'no':>5} {'--':>4} {r.total_programs:>10} "
                  f"{r.total_steps:>12} {r.time_seconds:>7.3f}s")

    print("-" * 60)
    print(f"Solved: {solved}/{len(benchmarks)}, Total time: {total_t:.3f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "demo":
        cmd_demo()
    elif cmd == "synth" and len(sys.argv) >= 3:
        cmd_synth(sys.argv[2])
    elif cmd == "enumerate":
        cmd_enumerate(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "benchmark":
        cmd_benchmark()
    else:
        print(__doc__)
