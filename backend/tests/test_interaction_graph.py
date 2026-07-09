import unittest
from datetime import datetime, timedelta

from interaction_graph import build_interaction_graph, compute_tau
from parser import Message


def message(author: str, timestamp: datetime) -> Message:
    return Message(author=author, timestamp=timestamp, text="x")


class ComputeTauTests(unittest.TestCase):
    def test_derived_from_gap_distribution_not_hardcoded(self) -> None:
        base = datetime(2026, 1, 1, 10, 0)
        fast_chat = [message("a", base + timedelta(seconds=10 * i)) for i in range(20)]
        slow_chat = [message("a", base + timedelta(hours=1 * i)) for i in range(20)]

        fast_tau = compute_tau(fast_chat)
        slow_tau = compute_tau(slow_chat)

        self.assertAlmostEqual(fast_tau, 10.0)
        self.assertAlmostEqual(slow_tau, 3600.0)
        self.assertLess(fast_tau, slow_tau)

    def test_single_message_falls_back_to_default(self) -> None:
        self.assertEqual(compute_tau([message("a", datetime(2026, 1, 1))]), 60.0)


class BuildInteractionGraphTests(unittest.TestCase):
    def test_close_pair_outweighs_isolated_member(self) -> None:
        base = datetime(2026, 1, 1, 10, 0)
        msgs = []
        t = base
        for _ in range(20):
            msgs.append(message("A", t))
            t += timedelta(seconds=30)
            msgs.append(message("B", t))
            t += timedelta(seconds=30)

        # C manda mensajes bien separados en el tiempo del bloque A/B (2 dias
        # antes, gaps de 5hs) -- no deberia generar ningun vinculo real.
        t2 = base - timedelta(days=2)
        for _ in range(5):
            msgs.append(message("C", t2))
            t2 += timedelta(hours=5)

        msgs.sort(key=lambda m: m.timestamp)
        graph = build_interaction_graph(msgs)

        edge_authors = {edge.source for edge in graph.edges} | {edge.target for edge in graph.edges}
        self.assertNotIn("C", edge_authors)

        ab_weight = max(edge.weight for edge in graph.edges if {edge.source, edge.target} == {"A", "B"})
        self.assertGreater(ab_weight, 0)
        self.assertEqual(graph.centrality["C"], 0.0)
        self.assertGreater(graph.centrality["A"], graph.centrality["C"])
        self.assertGreater(graph.centrality["B"], graph.centrality["C"])

    def test_two_temporal_cliques_are_detected_as_separate_communities(self) -> None:
        base = datetime(2026, 1, 1, 10, 0)
        msgs = []

        t = base
        for _ in range(20):
            msgs.append(message("A", t))
            t += timedelta(seconds=30)
            msgs.append(message("B", t))
            t += timedelta(seconds=30)

        # Segunda camarilla, 3 dias despues -- sin solapamiento temporal con la primera.
        t = base + timedelta(days=3)
        for _ in range(20):
            msgs.append(message("C", t))
            t += timedelta(seconds=30)
            msgs.append(message("D", t))
            t += timedelta(seconds=30)

        msgs.sort(key=lambda m: m.timestamp)
        graph = build_interaction_graph(msgs)

        community_sets = [set(community) for community in graph.communities]
        self.assertIn({"A", "B"}, community_sets)
        self.assertIn({"C", "D"}, community_sets)

    def test_empty_messages_returns_empty_graph(self) -> None:
        graph = build_interaction_graph([])

        self.assertEqual(graph.nodes, [])
        self.assertEqual(graph.edges, [])
        self.assertEqual(graph.centrality, {})
        self.assertEqual(graph.communities, [])


if __name__ == "__main__":
    unittest.main()
