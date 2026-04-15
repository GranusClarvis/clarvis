#!/usr/bin/env python3
"""Synaptic Memory — bridge to clarvis.memory.synaptic_memory."""
import runpy

if __name__ == "__main__":
    runpy.run_module("clarvis.memory.synaptic_memory", run_name="__main__")
