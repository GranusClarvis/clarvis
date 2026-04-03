# Changelog — clarvis-db

All notable changes to this package will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-03-17

### Added
- `VectorStore` — ChromaDB-backed vector memory with ONNX MiniLM embeddings
- `HebbianEngine` — co-activation tracking and importance reinforcement
- `STPDEngine` — spike-timing-dependent plasticity for temporal associations
- `ClarvisAdapter` — bridge to the Clarvis brain spine module
- CLI entry point (`clarvis-db`)
- Test suite covering store, recall, Hebbian learning, and STDP

### Deprecated
- Package deprecated in favour of `clarvis.brain` spine module (see `DEPRECATED.md`).
  The standalone package remains for its test suite and as a reference implementation.
