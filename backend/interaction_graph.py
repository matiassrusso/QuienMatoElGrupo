"""Grafo de interaccion (quien le responde a quien), inferido solo de
autor + timestamp -- nunca del contenido real de los mensajes."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

import networkx as nx

from parser import Message

# 60 min: mas alla de eso, un mensaje nuevo es mas probable que sea un tema
# distinto que una respuesta a quien hablo antes. No se deriva de la señal
# (a diferencia de tau) porque una ventana de "cuanto es razonable esperar
# una respuesta" es mas una convencion social que una propiedad del chat.
DEFAULT_REPLY_WINDOW_SECONDS = 60 * 60


@dataclass
class InteractionEdge:
    source: str
    target: str
    weight: float
    avg_latency_seconds: float


@dataclass
class InteractionGraph:
    nodes: list[str]
    edges: list[InteractionEdge]
    centrality: dict[str, float]
    communities: list[list[str]]


def compute_tau(messages: list[Message]) -> float:
    """Constante de decaimiento del peso de respuesta.

    Es la mediana de los gaps entre mensajes consecutivos del chat -- mismo
    espiritu que la penalizacion de PELT en build_phase_summary: un
    parametro de escala que sale de la señal real, no un valor magico fijo.
    Un chat lento (grupo grande, poco activo) tolera respuestas mas tardias
    antes de que el peso decaiga del todo; uno rapido y chico es mas
    exigente con la latencia.
    """
    gaps = [
        (curr.timestamp - prev.timestamp).total_seconds()
        for prev, curr in zip(messages, messages[1:])
    ]
    gaps = [gap for gap in gaps if gap > 0]
    if not gaps:
        return 60.0
    return max(statistics.median(gaps), 1.0)


def _bursts(messages: list[Message]) -> list[list[Message]]:
    """Agrupa rachas de mensajes consecutivos del mismo autor."""
    runs: list[list[Message]] = []
    for message in messages:
        if runs and runs[-1][-1].author == message.author:
            runs[-1].append(message)
        else:
            runs.append([message])
    return runs


def infer_edges(
    messages: list[Message], window_seconds: float = DEFAULT_REPLY_WINDOW_SECONDS
) -> tuple[list[InteractionEdge], float]:
    """Infere vinculos dirigidos B->A: B "gatilla" la racha de A si el gap
    entre el ultimo mensaje de B y el primer mensaje de A cae dentro de la
    ventana. Se compara racha contra racha (no mensaje contra mensaje) para
    que una rafaga de varios mensajes seguidos de A cuente una sola vez,
    contra el ultimo mensaje de la racha anterior -- no repartido entre
    todos los mensajes de A.
    """
    tau = compute_tau(messages)
    bursts = _bursts(messages)

    gaps_by_pair: dict[tuple[str, str], list[float]] = {}
    for previous, current in zip(bursts, bursts[1:]):
        gap = (current[0].timestamp - previous[-1].timestamp).total_seconds()
        if gap < 0 or gap > window_seconds:
            continue
        key = (previous[-1].author, current[0].author)
        gaps_by_pair.setdefault(key, []).append(gap)

    edges = [
        InteractionEdge(
            source=source,
            target=target,
            weight=round(sum(math.exp(-gap / tau) for gap in gaps), 4),
            avg_latency_seconds=round(statistics.mean(gaps), 2),
        )
        for (source, target), gaps in gaps_by_pair.items()
    ]
    return edges, tau


def build_interaction_graph(
    messages: list[Message], window_seconds: float = DEFAULT_REPLY_WINDOW_SECONDS
) -> InteractionGraph:
    authors = sorted({message.author for message in messages})
    if not authors:
        return InteractionGraph(nodes=[], edges=[], centrality={}, communities=[])

    edges, _tau = infer_edges(messages, window_seconds)

    if not edges:
        return InteractionGraph(
            nodes=authors,
            edges=[],
            centrality={author: 0.0 for author in authors},
            communities=[[author] for author in authors],
        )

    graph = nx.DiGraph()
    graph.add_nodes_from(authors)
    for edge in edges:
        graph.add_edge(edge.source, edge.target, weight=edge.weight)

    # eigenvector_centrality capta "quien sostiene la conversacion" mejor que
    # degree_centrality: no solo cuenta cuantos vinculos tiene alguien, sino
    # si esos vinculos vienen de gente que a su vez esta bien conectada (eco
    # real dentro del grupo, no solo volumen de respuestas). Cae a
    # degree_centrality si el grafo no converge (tipico en grafos muy
    # dispersos o con componentes chicas).
    try:
        centrality = nx.eigenvector_centrality(graph, weight="weight", max_iter=1000)
    except (nx.PowerIterationFailedConvergence, nx.AmbiguousSolution):
        centrality = nx.degree_centrality(graph)

    undirected = graph.to_undirected()
    community_sets = nx.algorithms.community.greedy_modularity_communities(undirected, weight="weight")
    communities = [sorted(community) for community in community_sets]

    return InteractionGraph(
        nodes=authors,
        edges=edges,
        centrality={author: round(score, 4) for author, score in centrality.items()},
        communities=communities,
    )
