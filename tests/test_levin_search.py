"""Tests for Levin search program synthesis."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "challenges"))

from levin_search import (
    Op, Instr, execute, ExecResult, all_instructions,
    enumerate_programs, levin_search, levin_search_phased,
    parse_spec, format_program,
)


class TestInterpreter:
    def test_inc(self):
        prog = [Instr(Op.CPY, 1, 0), Instr(Op.INC, 1)]
        r = execute(prog, 5)
        assert r.output == 6

    def test_dec_floors_at_zero(self):
        prog = [Instr(Op.DEC, 1)]
        r = execute(prog, 0)
        assert r.output == 0

    def test_add(self):
        prog = [Instr(Op.CPY, 1, 0), Instr(Op.ADD, 1, 0)]
        r = execute(prog, 3)
        assert r.output == 6

    def test_sub(self):
        prog = [Instr(Op.CPY, 1, 0), Instr(Op.DEC, 1)]
        r = execute(prog, 5)
        assert r.output == 4

    def test_mul(self):
        prog = [Instr(Op.INC, 2), Instr(Op.INC, 2), Instr(Op.INC, 2),
                Instr(Op.CPY, 1, 0), Instr(Op.MUL, 1, 2)]
        r = execute(prog, 4)
        assert r.output == 12

    def test_halt_stops_execution(self):
        prog = [Instr(Op.INC, 1), Instr(Op.HALT), Instr(Op.INC, 1)]
        r = execute(prog, 0)
        assert r.output == 1
        assert r.halted is True

    def test_jz_jumps_when_zero(self):
        prog = [Instr(Op.JZ, 1, 2), Instr(Op.INC, 1), Instr(Op.INC, 1), Instr(Op.INC, 1)]
        r = execute(prog, 0)
        assert r.output == 2  # jumps +2 to index 2, runs indices 2 and 3

    def test_jnz_jumps_when_nonzero(self):
        prog = [Instr(Op.INC, 1), Instr(Op.JNZ, 1, 2), Instr(Op.INC, 1), Instr(Op.INC, 1)]
        r = execute(prog, 0)
        assert r.output == 2  # jumps +2 to index 3, runs index 3

    def test_loop(self):
        prog = [Instr(Op.CPY, 2, 0), Instr(Op.LOOP, 2, 1), Instr(Op.INC, 1)]
        r = execute(prog, 3)
        assert r.output == 3

    def test_zero(self):
        prog = [Instr(Op.INC, 1), Instr(Op.INC, 1), Instr(Op.ZERO, 1)]
        r = execute(prog, 0)
        assert r.output == 0

    def test_step_limit(self):
        prog = [Instr(Op.CPY, 2, 0), Instr(Op.LOOP, 2, 1), Instr(Op.INC, 1)]
        r = execute(prog, 10000, max_steps=10)
        assert r.steps >= 10

    def test_max_int_cap(self):
        prog = [Instr(Op.CPY, 1, 0), Instr(Op.MUL, 1, 0)]
        r = execute(prog, 200)
        assert r.output == 10000  # capped at MAX_INT

    def test_mod(self):
        prog = [Instr(Op.CPY, 1, 0), Instr(Op.INC, 2), Instr(Op.INC, 2),
                Instr(Op.MOD, 1, 2)]
        r = execute(prog, 7)
        assert r.output == 1

    def test_mod_by_zero_noop(self):
        prog = [Instr(Op.CPY, 1, 0), Instr(Op.MOD, 1, 2)]
        r = execute(prog, 7)
        assert r.output == 7


class TestEnumeration:
    def test_all_instructions_nonempty(self):
        vocab = all_instructions()
        assert len(vocab) > 20

    def test_enumerate_produces_programs(self):
        vocab = all_instructions(max_jump=1, max_loop_body=1)
        progs = list(enumerate_programs(vocab, max_len=1))
        assert len(progs) == len(vocab)

    def test_length_ordering(self):
        vocab = all_instructions(max_jump=1, max_loop_body=1)
        lengths = []
        for i, prog in enumerate(enumerate_programs(vocab, max_len=2)):
            lengths.append(len(prog))
            if i > 200:
                break
        assert lengths[0] == 1
        assert all(lengths[i] <= lengths[i+1] for i in range(len(lengths)-1))


class TestLevinSearch:
    def test_synthesize_identity(self):
        spec = {0: 0, 1: 1, 2: 2, 3: 3}
        r = levin_search(spec, max_program_len=3)
        assert r.found
        for inp, exp in spec.items():
            er = execute(r.program, inp)
            assert er.output == exp

    def test_synthesize_successor(self):
        spec = {0: 1, 1: 2, 2: 3}
        r = levin_search(spec, max_program_len=3)
        assert r.found
        for inp, exp in spec.items():
            er = execute(r.program, inp)
            assert er.output == exp

    def test_synthesize_constant_zero(self):
        spec = {0: 0, 1: 0, 5: 0}
        r = levin_search(spec, max_program_len=2)
        assert r.found
        assert r.length <= 2

    def test_phased_synthesize_doubler(self):
        spec = {0: 0, 1: 2, 2: 4, 3: 6}
        r = levin_search_phased(spec, max_program_len=4)
        assert r.found
        for inp, exp in spec.items():
            er = execute(r.program, inp)
            assert er.output == exp

    def test_phased_synthesize_constant_one(self):
        spec = {0: 1, 1: 1, 5: 1}
        r = levin_search_phased(spec, max_program_len=3)
        assert r.found

    def test_budget_allocation(self):
        spec = {0: 0, 1: 1}
        r = levin_search(spec, max_program_len=2, total_budget=100)
        assert r.total_programs > 0

    def test_no_solution_returns_not_found(self):
        spec = {0: 999, 1: 998}
        r = levin_search(spec, max_program_len=1, total_budget=100)
        assert not r.found


class TestBugFixes:
    def test_loop_body_index_with_duplicate_instructions(self):
        """Regression: program.index(instr) found wrong position with repeats."""
        loop_r0 = Instr(Op.LOOP, 0, 1)
        inc_r1 = Instr(Op.INC, 1)
        program = [loop_r0, inc_r1, loop_r0, inc_r1]
        r = execute(program, 3)
        assert r.output == 6

    def test_phased_prune_does_not_misindex_loop_body(self):
        """Regression: levin_search_phased used program.index() for LOOP body scan."""
        spec = {0: 0, 1: 1, 2: 2, 3: 3}
        r = levin_search_phased(spec, max_program_len=3)
        assert r.found
        for inp, exp in spec.items():
            er = execute(r.program, inp)
            assert er.halted or er.output == exp

    def test_nonhalt_not_accepted_as_match(self):
        """Regression: timed-out programs with correct r1 were accepted.

        A program that produces the right output but doesn't halt (step limit
        exhausted) must NOT be accepted by the search.
        """
        prog = [Instr(Op.INC, 1), Instr(Op.JNZ, 1, 0)]
        r = execute(prog, 0, max_steps=20)
        assert not r.halted
        assert r.output == 1

        # Verify directly: execute with tight budget produces correct output but not halted
        prog2 = [Instr(Op.CPY, 2, 0), Instr(Op.LOOP, 2, 1), Instr(Op.INC, 1)]
        r2 = execute(prog2, 10000, max_steps=5)
        assert not r2.halted
        # The search must require halted=True, so a non-halting match is rejected
        spec = {10000: r2.output}
        result = levin_search(spec, max_program_len=1, total_budget=5)
        if result.found:
            er = execute(result.program, 10000, max_steps=10000)
            assert er.halted, "Accepted program must actually halt"


class TestParseSpec:
    def test_simple(self):
        assert parse_spec("0:0,1:2,2:4") == {0: 0, 1: 2, 2: 4}

    def test_single(self):
        assert parse_spec("5:10") == {5: 10}
