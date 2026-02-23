"""CLI for ClarvisDB."""

import json
import sys


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: clarvis-db <command> [args]")
        print()
        print("Commands:")
        print("  stats [data_dir]          Show store statistics")
        print("  store <text> [data_dir]   Store a memory")
        print("  recall <query> [data_dir] Search memories")
        print("  evolve [data_dir]         Run Hebbian + STDP evolution")
        print("  consolidate [data_dir]    Run STDP consolidation")
        print("  hubs [data_dir]           Show hub memories")
        print("  strongest [data_dir]      Show strongest synapses")
        print("  test                      Run self-test with temp data")
        sys.exit(1)

    cmd = args[0]

    if cmd == "test":
        _self_test()
        return

    from clarvis_db import VectorStore

    data_dir = args[-1] if len(args) > 1 and not args[-1].startswith("-") else "./data/clarvisdb"
    # For store/recall, data_dir is 3rd arg
    if cmd in ("store", "recall") and len(args) >= 3:
        data_dir = args[2]
    elif cmd in ("store", "recall") and len(args) == 2:
        data_dir = "./data/clarvisdb"

    db = VectorStore(data_dir=data_dir, collections=["memories"])

    if cmd == "stats":
        print(json.dumps(db.stats(), indent=2))

    elif cmd == "store":
        if len(args) < 2:
            print("Usage: store <text> [data_dir]")
            sys.exit(1)
        mid = db.store(args[1])
        print(f"Stored: {mid}")

    elif cmd == "recall":
        if len(args) < 2:
            print("Usage: recall <query> [data_dir]")
            sys.exit(1)
        results = db.recall(args[1])
        for r in results:
            print(f"  [{r['collection']}] {r['document'][:80]}")

    elif cmd == "evolve":
        result = db.evolve()
        print(json.dumps(result, indent=2))

    elif cmd == "consolidate":
        if db.synaptic:
            result = db.synaptic.consolidate()
            print(json.dumps(result, indent=2))
        else:
            print("STDP engine not available")

    elif cmd == "hubs":
        if db.synaptic:
            hubs = db.synaptic.get_hubs()
            for h in hubs:
                print(f"  fan_out={h['fan_out']:3d}  avg_w={h['avg_weight']:.3f}  {h['memory_id']}")
        else:
            print("STDP engine not available")

    elif cmd == "strongest":
        if db.synaptic:
            for s in db.synaptic.get_strongest():
                print(f"  w={s['weight']:.4f}  {s['pre'][:30]} -> {s['post'][:30]}")
        else:
            print("STDP engine not available")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


def _self_test():
    """Run a quick self-test with temporary data."""
    import tempfile
    import os

    print("=== ClarvisDB Self-Test ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        from clarvis_db import VectorStore, HebbianEngine, SynapticEngine

        # 1. Hebbian engine standalone
        print("1. Hebbian engine:")
        heb = HebbianEngine(data_dir=os.path.join(tmpdir, "heb"))
        imp = heb.reinforce("test_mem", 0.5, 1)
        print(f"   Reinforced: 0.5 -> {imp}")
        decayed = heb.compute_decay(0.8, days_since_access=10, access_count=0)
        print(f"   Decay (10 days, 0 accesses): 0.8 -> {decayed}")
        decayed2 = heb.compute_decay(0.8, days_since_access=10, access_count=10)
        print(f"   Decay (10 days, 10 accesses): 0.8 -> {decayed2}")
        assert decayed2 > decayed, "High access count should slow decay"
        print("   OK\n")

        # 2. STDP engine standalone
        print("2. STDP engine:")
        syn = SynapticEngine(db_path=os.path.join(tmpdir, "syn", "test.db"))
        w1 = syn.potentiate("a", "b", delta_t=0)
        w2 = syn.potentiate("a", "b", delta_t=0)
        w3 = syn.potentiate("a", "b", delta_t=0)
        print(f"   3x potentiate: 0.1 -> {w1:.4f} -> {w2:.4f} -> {w3:.4f}")
        assert w3 > w1, "Repeated potentiation should increase weight"
        d1 = syn.depress("a", "b")
        print(f"   Depress: {w3:.4f} -> {d1:.4f}")
        assert d1 < w3, "Depression should decrease weight"

        # Spreading activation
        for i in range(5):
            syn.potentiate("hub", f"t{i}", delta_t=0)
        spread = syn.spread("hub", n=5)
        print(f"   Spread from hub: {len(spread)} targets")
        assert len(spread) == 5
        print("   OK\n")

        # 3. Memristor transfer function
        print("3. Memristor roundtrip:")
        for state in [0.0, 0.25, 0.5, 0.75, 1.0]:
            w = SynapticEngine.memristor_weight(state)
            s_back = SynapticEngine.inverse_memristor(w)
            ok = abs(s_back - state) < 0.01
            print(f"   state={state:.2f} -> w={w:.4f} -> state={s_back:.2f} {'OK' if ok else 'FAIL'}")
            assert ok, f"Roundtrip failed for state={state}"
        print()

        # 4. Full VectorStore
        print("4. VectorStore integration:")
        db = VectorStore(
            data_dir=os.path.join(tmpdir, "db"),
            collections=["facts", "episodes"],
        )
        mid1 = db.store("The Earth orbits the Sun in 365 days", collection="facts", importance=0.9)
        mid2 = db.store("Mars has two moons: Phobos and Deimos", collection="facts", importance=0.7)
        mid3 = db.store("Debug session: fixed auth timeout", collection="episodes")
        print(f"   Stored 3 memories")

        results = db.recall("planetary orbits")
        print(f"   Recall 'planetary orbits': {len(results)} results")
        if results:
            print(f"   Top: {results[0]['document'][:60]}")

        s = db.stats()
        print(f"   Stats: {s['total_memories']} memories, {s['graph_edges']} edges")

        # Evolution
        evo = db.evolve()
        print(f"   Evolution: hebbian scanned={evo.get('hebbian', {}).get('total_scanned', 'N/A')}")

        # Associative recall
        assoc = db.associative_recall([mid1])
        print(f"   Associative recall from {mid1[:20]}: {len(assoc)} associated")

        print("   OK\n")

        # 5. Consolidation
        print("5. STDP consolidation:")
        result = db.synaptic.consolidate()
        print(f"   Synapses: {result['total_synapses']}, avg_weight: {result['avg_weight']}")
        print("   OK\n")

    print("=== All self-tests passed ===")


if __name__ == "__main__":
    main()
