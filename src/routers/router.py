from __future__ import annotations

import csv
import heapq
import os
from typing import Dict, List, Tuple


class LinkStateRouter:
    def __init__(self, node_id: str, neighbors: Dict[str, int], host: str = "127.0.0.1", port: int = 5000):
        self.node_id = node_id
        self.neighbors = neighbors
        self.host = host
        self.port = port
        self.lsa_seq = 0
        self.topology: Dict[str, Dict[str, int]] = {node_id: dict(neighbors)}
        self.latest_lsas: Dict[str, Tuple[int, Dict[str, int]]] = {}
        self.routing_table: Dict[str, Tuple[str, int, str, int]] = {}
        self.seen_sequences: Dict[str, int] = {}
        self.hello_counter = 0

    def build_lsa(self) -> dict:
        self.lsa_seq += 1
        return {
            "type": "LSA",
            "origin": self.node_id,
            "seq": self.lsa_seq,
            "links": [{"to": neighbor, "cost": cost} for neighbor, cost in self.neighbors.items()],
            "from": self.node_id,
        }

    def build_hello(self) -> dict:
        self.hello_counter += 1
        return {"type": "HELLO", "from": self.node_id, "seq": self.hello_counter}

    def process_hello(self, hello: dict) -> None:
        if hello.get("type") != "HELLO":
            return
        self.topology.setdefault(hello["from"], {})

    def process_lsa(self, lsa: dict, sender: str | None = None) -> bool:
        if lsa.get("type") != "LSA":
            return False
        origin = lsa["origin"]
        seq = int(lsa["seq"])
        previous_seq = self.seen_sequences.get(origin)
        if previous_seq is not None and seq <= previous_seq:
            return False
        self.seen_sequences[origin] = seq
        self.latest_lsas[origin] = (seq, {link["to"]: int(link["cost"]) for link in lsa.get("links", [])})
        self._rebuild_topology()
        self._write_routing_table()
        return True

    def flood_lsa(self, lsa: dict, sender: str | None = None) -> List[Tuple[str, dict]]:
        if self.process_lsa(lsa, sender):
            forwarded = []
            for neighbor in self.neighbors:
                if sender and neighbor == sender:
                    continue
                forwarded.append((neighbor, lsa))
            return forwarded
        return []

    def _rebuild_topology(self) -> None:
        topology: Dict[str, Dict[str, int]] = {self.node_id: dict(self.neighbors)}
        for origin, links in self.latest_lsas.items():
            adjacency = dict(links[1])
            topology[origin] = adjacency
            for neighbor in adjacency:
                topology.setdefault(neighbor, {})
            topology.setdefault(origin, {})
        for node in list(topology):
            for neighbor in list(topology[node]):
                topology.setdefault(neighbor, {})
        self.topology = topology

    def _write_routing_table(self) -> None:
        paths = compute_shortest_paths(self.topology, self.node_id)
        self.routing_table = {}
        for dest, (next_hop, cost) in paths.items():
            if dest == self.node_id:
                continue
            self.routing_table[dest] = (next_hop, cost, self.host, self.port + 1000 + len(dest))

        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{self.node_id}_nodo_tabla_enrutamiento.csv")
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["destino", "siguiente_salto", "costo", "ip", "puerto"])
            for dest, (next_hop, cost, ip, port) in self.routing_table.items():
                writer.writerow([dest, next_hop, cost, ip, port])

    def forward_data_packet(self, packet: dict) -> dict:
        if packet.get("nodo_destino") in self.routing_table:
            next_hop, _, ip, port = self.routing_table[packet["nodo_destino"]]
            return {"next_hop": next_hop, "ip": ip, "port": port, "packet": packet}
        return {"next_hop": None, "ip": None, "port": None, "packet": packet}


def compute_shortest_paths(graph: Dict[str, Dict[str, int]], source: str) -> Dict[str, Tuple[str, int]]:
    nodes = set(graph.keys())
    for neighbors in graph.values():
        nodes.update(neighbors.keys())

    distances = {node: float("inf") for node in nodes}
    distances[source] = 0
    previous: Dict[str, str] = {}
    priority_queue = [(0, source)]

    while priority_queue:
        current_cost, node = heapq.heappop(priority_queue)
        if current_cost > distances[node]:
            continue
        for neighbor, weight in graph.get(node, {}).items():
            candidate_cost = current_cost + weight
            if candidate_cost < distances[neighbor]:
                distances[neighbor] = candidate_cost
                previous[neighbor] = node
                heapq.heappush(priority_queue, (candidate_cost, neighbor))

    paths = {}
    for node in nodes:
        if node == source or distances[node] == float("inf"):
            continue
        next_hop = node
        current = node
        while previous.get(current) is not None and previous[current] != source:
            current = previous[current]
        if previous.get(current) == source:
            next_hop = current
        paths[node] = (next_hop, int(distances[node]))
    return paths
