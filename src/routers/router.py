from __future__ import annotations

import csv
import heapq
import os
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from common.framing import recv_packet, send_packet


class LinkStateRouter:
    def __init__(
        self,
        node_id: str,
        neighbors: Dict[str, int],
        host: str = "127.0.0.1",
        port: int = 5000,
        node_addresses: Optional[Dict[str, Tuple[str, int]]] = None,
        hello_interval: float = 2.0,
        lsa_interval: float = 10.0,
        dead_interval: float = 6.0,
    ):
        self.node_id = node_id
        # neighbors mapping: neighbor_id -> cost
        self.neighbors: Dict[str, int] = dict(neighbors)
        self.initial_neighbors: Dict[str, int] = dict(neighbors)
        self.host = host
        self.port = port
        # node_addresses mapping: node_id -> (host, port)
        self.node_addresses: Dict[str, Tuple[str, int]] = node_addresses or {}
        self.node_addresses[node_id] = (host, port)

        self.hello_interval = hello_interval
        self.lsa_interval = lsa_interval
        self.dead_interval = dead_interval

        self.lsa_seq = 0
        self.hello_counter = 0
        self.seen_sequences: Dict[str, int] = {}
        self.latest_lsas: Dict[str, Tuple[int, List[Dict[str, Any]]]] = {}
        
        # Local topology graph: node_id -> {neighbor_id: cost}
        self.topology: Dict[str, Dict[str, int]] = {self.node_id: dict(self.neighbors)}
        
        # Routing table: dest -> (next_hop, cost, ip, port)
        self.routing_table: Dict[str, Tuple[str, int, str, int]] = {}
        self.neighbor_last_seen: Dict[str, float] = {}

        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.threads: List[threading.Thread] = []
        self.lock = threading.Lock()

        # Generate initial self LSA state
        self._update_self_lsa_state()

    def _update_self_lsa_state(self) -> None:
        self.topology[self.node_id] = dict(self.neighbors)
        self.latest_lsas[self.node_id] = (
            self.lsa_seq,
            [{"to": n, "cost": c} for n, c in self.neighbors.items()],
        )

    def build_hello(self) -> dict:
        with self.lock:
            self.hello_counter += 1
            return {"type": "HELLO", "from": self.node_id, "cost": 1, "seq": self.hello_counter}

    def build_lsa(self) -> dict:
        with self.lock:
            self.lsa_seq += 1
            links = [{"to": neighbor, "cost": cost} for neighbor, cost in self.neighbors.items()]
            lsa = {
                "type": "LSA",
                "origin": self.node_id,
                "seq": self.lsa_seq,
                "links": links,
                "from": self.node_id,
            }
            self.seen_sequences[self.node_id] = self.lsa_seq
            self.latest_lsas[self.node_id] = (self.lsa_seq, links)
            return lsa

    def process_hello(self, hello: dict) -> None:
        if hello.get("type") != "HELLO":
            return
        sender = hello.get("from")
        if not sender or sender == self.node_id:
            return

        with self.lock:
            now = time.time()
            self.neighbor_last_seen[sender] = now
            cost = int(hello.get("cost", 1))

            # If neighbor was marked down or is new, restore/add link
            changed = False
            if sender not in self.neighbors or self.neighbors[sender] != cost:
                self.neighbors[sender] = cost
                changed = True

            if changed:
                self._update_self_lsa_state()
                self._rebuild_topology_and_routes()
                lsa = self.build_lsa()
                self.flood_lsa(lsa, sender=self.node_id)

    def process_lsa(self, lsa: dict, sender: Optional[str] = None) -> bool:
        if lsa.get("type") != "LSA":
            return False
        origin = lsa.get("origin")
        if not origin or "seq" not in lsa:
            return False

        seq = int(lsa["seq"])
        with self.lock:
            previous_seq = self.seen_sequences.get(origin)
            if previous_seq is not None and seq <= previous_seq:
                return False

            self.seen_sequences[origin] = seq
            links = lsa.get("links", [])
            self.latest_lsas[origin] = (seq, links)
            self._rebuild_topology_and_routes()
            return True

    def flood_lsa(self, lsa: dict, sender: Optional[str] = None) -> List[Tuple[str, dict]]:
        lsa_to_send = dict(lsa)
        lsa_to_send["from"] = self.node_id
        
        is_new = self.process_lsa(lsa, sender)
        forwarded = []
        if is_new or lsa.get("origin") == self.node_id:
            with self.lock:
                active_neighbors = list(self.neighbors.keys())

            for neighbor in active_neighbors:
                if sender and neighbor == sender:
                    continue
                forwarded.append((neighbor, lsa_to_send))
                if self.running:
                    threading.Thread(
                        target=self._send_to_node,
                        args=(neighbor, lsa_to_send),
                        daemon=True,
                    ).start()
        return forwarded

    def _rebuild_topology_and_routes(self) -> None:
        # Reconstruct graph from latest LSAs
        topology: Dict[str, Dict[str, int]] = {self.node_id: dict(self.neighbors)}
        for origin, (_, links) in self.latest_lsas.items():
            adjacency = {link["to"]: int(link["cost"]) for link in links if "to" in link}
            topology[origin] = adjacency
            for neighbor in adjacency:
                topology.setdefault(neighbor, {})
            topology.setdefault(origin, {})

        self.topology = topology
        self._write_routing_table()

    def _write_routing_table(self) -> None:
        paths = compute_shortest_paths(self.topology, self.node_id)
        routing_table = {}
        for dest, (next_hop, cost) in paths.items():
            if dest == self.node_id:
                continue
            ip, port = self.node_addresses.get(next_hop, (self.host, self.port + 1000 + len(dest)))
            routing_table[dest] = (next_hop, cost, ip, port)

        self.routing_table = routing_table

        # Escribir CSV en disco sin bloquear locks
        threading.Thread(
            target=self._save_csv_disk,
            args=(dict(routing_table),),
            daemon=True,
        ).start()

    def _save_csv_disk(self, table: Dict[str, Tuple[str, int, str, int]]) -> None:
        try:
            output_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{self.node_id}_nodo_tabla_enrutamiento.csv")
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["destino", "siguiente_salto", "costo", "ip", "puerto"])
                for dest, (next_hop, cost, ip, port) in table.items():
                    writer.writerow([dest, next_hop, cost, ip, port])
        except Exception:
            pass

    def forward_data_packet(self, packet: dict) -> dict:
        dest = packet.get("nodo_destino")
        with self.lock:
            route = self.routing_table.get(dest) if dest else None
        if route:
            next_hop, _, ip, port = route
            return {"next_hop": next_hop, "ip": ip, "port": port, "packet": packet}
        return {"next_hop": None, "ip": None, "port": None, "packet": packet}

    def start(self) -> None:
        """Inicia el servidor TCP y los hilos de fondo del router."""
        if self.running:
            return
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)

        t_server = threading.Thread(target=self._server_loop, daemon=True, name=f"{self.node_id}-server")
        t_hello = threading.Thread(target=self._hello_loop, daemon=True, name=f"{self.node_id}-hello")
        t_liveness = threading.Thread(target=self._liveness_loop, daemon=True, name=f"{self.node_id}-liveness")
        t_lsa_periodic = threading.Thread(target=self._lsa_periodic_loop, daemon=True, name=f"{self.node_id}-lsa-period")

        self.threads = [t_server, t_hello, t_liveness, t_lsa_periodic]
        for t in self.threads:
            t.start()

        # Emitir LSA inicial tras levantar el servidor TCP
        lsa = self.build_lsa()
        self.flood_lsa(lsa, sender=self.node_id)

    def stop(self) -> None:
        """Detiene el router y cierra sus sockets."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def _server_loop(self) -> None:
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_sock,),
                    daemon=True,
                ).start()
            except Exception:
                if not self.running:
                    break

    def _handle_client(self, client_sock: socket.socket) -> None:
        with client_sock:
            while self.running:
                packet = recv_packet(client_sock)
                if packet is None:
                    break
                self._handle_packet(packet)

    def _handle_packet(self, packet: dict) -> None:
        p_type = packet.get("type")
        if p_type == "HELLO":
            self.process_hello(packet)
        elif p_type == "LSA":
            sender = packet.get("from")
            self.flood_lsa(packet, sender=sender)
        elif "nodo_destino" in packet:
            # Data packet
            dest = packet["nodo_destino"]
            if dest == self.node_id:
                print(f"[{self.node_id}] Paquete de datos recibido para mí:", packet)
            else:
                route_info = self.forward_data_packet(packet)
                next_hop = route_info["next_hop"]
                if next_hop:
                    ip, port = route_info["ip"], route_info["port"]
                    self._send_to_address(ip, port, packet)
                else:
                    print(f"[{self.node_id}] ERROR: No hay ruta hacia {dest}")

    def _send_to_node(self, target_id: str, packet: dict) -> bool:
        addr = self.node_addresses.get(target_id)
        if not addr:
            return False
        return self._send_to_address(addr[0], addr[1], packet)

    def _send_to_address(self, ip: str, port: int, packet: dict) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((ip, port))
                send_packet(s, packet)
                return True
        except Exception:
            return False

    def _hello_loop(self) -> None:
        time.sleep(0.5)
        while self.running:
            hello_msg = self.build_hello()
            with self.lock:
                target_neighbors = list(self.neighbors.keys())
            for neighbor_id in target_neighbors:
                threading.Thread(
                    target=self._send_to_node,
                    args=(neighbor_id, hello_msg),
                    daemon=True,
                ).start()
            time.sleep(self.hello_interval)

    def _liveness_loop(self) -> None:
        while self.running:
            time.sleep(1.0)
            now = time.time()
            changed = False
            with self.lock:
                for neighbor_id in list(self.neighbors.keys()):
                    last = self.neighbor_last_seen.get(neighbor_id)
                    if last is not None and (now - last) > self.dead_interval:
                        print(f"[{self.node_id}] VECINO CAÍDO: {neighbor_id} (sin HELLO por > {self.dead_interval}s)")
                        del self.neighbors[neighbor_id]
                        changed = True

                if changed:
                    self._update_self_lsa_state()
                    self._rebuild_topology_and_routes()
            if changed:
                lsa = self.build_lsa()
                self.flood_lsa(lsa, sender=self.node_id)

    def _lsa_periodic_loop(self) -> None:
        while self.running:
            time.sleep(self.lsa_interval)
            lsa = self.build_lsa()
            self.flood_lsa(lsa, sender=self.node_id)


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
