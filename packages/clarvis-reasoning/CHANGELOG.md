# Changelog — clarvis-reasoning

All notable changes to this package will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-02-15

### Added
- `check_step_quality()` — evaluate individual reasoning step quality
- `evaluate_session()` — session-level reasoning quality assessment
- `diagnose_sessions()` — cross-session reasoning pattern diagnosis
- `compute_coherence()` — measure reasoning chain coherence
- Based on Flavell (1979) metacognition and Dunlosky & Metcalfe (2009)
- CLI entry point (`clarvis-reasoning`) with `check`, `evaluate`, `diagnose` commands
- Test suite covering metacognition scoring and CLI
