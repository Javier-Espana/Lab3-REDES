from __future__ import annotations

import csv
import heapq
import os
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from common.framing import recv_packet, send_packet

_VERBOSE = True


def set_router_verbose(enabled: bool) -> None:
    global _VERBOSE
    _VERBOSE = enabled


def get_router_verbose() -> bool:
    return _VERBOSE


def router_print(*args, **kwargs) -> None:
    if _VERBOSE:
        print(*args, **kwargs)


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
        dead_interval: float = 15.0,
    ):
        self.node_id = node_id
        self.neighbors: Dict[str, int] = dict(neighbors)
        self.initial_neighbors: Dict[str, int] = dict(neighbors)
        self.host = host
        self.port = port
        self.node_addresses: Dict[str, Tuple[str, int]] = node_addresses or {}
        self.node_addresses[node_id] = (host, port)

        self.hello_interval = hello_interval
        self.lsa_interval = lsa_interval
        self.dead_interval = dead_interval

        self.lsa_seq = 0
        self.hello_counter = 0
        self.seen_sequences: Dict[str, int] = {}
        self.latest_lsas: Dict[str, Tuple[int, List[Dict[str, Any]]]] = {}

        self.topology: Dict[str, Dict[str, int]] = {self.node_id: dict(self.neighbors)}
        self.routing_table: Dict[str, Tuple[str, int, str, int, List[str]]] = {}
        self.neighbor_last_seen: Dict[str, float] = {}

        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.threads: List[threading.Thread] = []
        self.lock = threading.Lock()

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
            return {"type": "HELLO", "from": self.node_id}

    def _build_lsa_nolock(self) -> dict:
        """Construye un LSA. Llamar solo cuando ya se tiene self.lock."""
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

    def build_lsa(self) -> dict:
        with self.lock:
            return self._build_lsa_nolock()

    def process_hello(self, hello: dict) -> None:
        if hello.get("type") != "HELLO":
            return
        sender = hello.get("from")
        if not sender or sender == self.node_id:
            return

        router_print(f"[{self.node_id}] HELLO recibido de {sender}", flush=True)

        lsa_to_flood = None
        with self.lock:
            now = time.time()
            is_first = sender not in self.neighbor_last_seen
            self.neighbor_last_seen[sender] = now
            cost = int(hello.get("cost", 1))

            if is_first:
                router_print(f"[{self.node_id}] Vecino detectado: {sender}", flush=True)

            changed = False
            if sender not in self.neighbors or self.neighbors[sender] != cost:
                self.neighbors[sender] = cost
                changed = True

            if changed or is_first:
                if changed and not is_first:
                    router_print(f"[{self.node_id}] Enlace actualizado con {sender}", flush=True)
                self._update_self_lsa_state()
                self._rebuild_topology_and_routes()
                lsa_to_flood = self._build_lsa_nolock()

        # Flood LSA fuera del lock para evitar deadlock
        if lsa_to_flood:
            self.flood_lsa(lsa_to_flood, sender=self.node_id)

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

        origin = lsa.get("origin")
        seq = lsa.get("seq", 0)
        links = lsa.get("links", [])
        is_own = origin == self.node_id

        if is_own and sender == self.node_id:
            router_print(f"[{self.node_id}] Publicando LSA seq={seq} con {len(links)} enlaces activos", flush=True)

        is_new = is_own or self.process_lsa(lsa, sender)
        forwarded = []
        if is_new:
            if not is_own:
                router_print(f"[{self.node_id}] LSA recibido de {origin} (seq={seq}, {len(links)} enlaces)", flush=True)
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
        """Reconstruye la topologia y la tabla de rutas. Llamar dentro del lock."""
        topology: Dict[str, Dict[str, int]] = {self.node_id: dict(self.neighbors)}
        for origin, (_, links) in self.latest_lsas.items():
            adjacency = {link["to"]: int(link["cost"]) for link in links if "to" in link}
            topology[origin] = adjacency
            for neighbor in adjacency:
                topology.setdefault(neighbor, {})
            topology.setdefault(origin, {})
        self.topology = topology
        # _write_routing_table no adquiere lock, puede llamarse dentro
        self._write_routing_table()

    def _write_routing_table(self) -> None:
        """Calcula rutas Dijkstra y actualiza self.routing_table. Llamar dentro del lock."""
        paths = compute_shortest_paths(self.topology, self.node_id)
        routing_table = {}
        for dest, (next_hop, cost, path) in paths.items():
            if dest == self.node_id:
                continue
            addr = self.node_addresses.get(next_hop)
            if addr:
                ip, port = addr
            else:
                ip, port = self.host, self.port + 1000
            routing_table[dest] = (next_hop, cost, ip, port, path)

        changed = routing_table != self.routing_table
        self.routing_table = routing_table

        if changed:
            router_print(f"[{self.node_id}] Tabla de ruteo actualizada ({len(routing_table)} destinos):", flush=True)
            for dest, (nh, cost, ip, port, path) in routing_table.items():
                router_print(f"   {dest} -> next_hop={nh} cost={cost} path={' -> '.join(path)}", flush=True)
            threading.Thread(target=self._save_csv_disk, args=(dict(routing_table),), daemon=True).start()

    def _save_csv_disk(self, table: Dict[str, Tuple[str, int, str, int, List[str]]]) -> None:
        try:
            output_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(output_dir, exist_ok=True)
            target_files = [
                os.path.join(output_dir, f"{self.node_id}_nodo_tabla_enrutamiento.csv"),
                os.path.join(output_dir, f"{self.node_id}_tabla_enrutamiento.csv"),
                os.path.join(os.getcwd(), f"{self.node_id}_tabla_enrutamiento.csv"),
            ]
            for path in target_files:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["destino", "siguiente_salto", "costo", "ip", "puerto"])
                    for dest, (next_hop, cost, ip, port, _) in table.items():
                        writer.writerow([dest, next_hop, cost, ip, port])
        except Exception:
            pass

    def forward_data_packet(self, packet: dict) -> dict:
        dest = packet.get("nodo_destino")
        with self.lock:
            route = self.routing_table.get(dest) if dest else None
        if route and len(route) >= 4:
            next_hop, cost, ip, port = route[0], route[1], route[2], route[3]
            return {"next_hop": next_hop, "cost": cost, "ip": ip, "port": port}
        return {"next_hop": None, "cost": 0, "ip": None, "port": None}

    def start(self) -> None:
        """Inicia el servidor TCP y los hilos de fondo del router."""
        if self.running:
            return
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(20)

        self.threads = [
            threading.Thread(target=self._server_loop, daemon=True, name=f"{self.node_id}-server"),
            threading.Thread(target=self._hello_loop, daemon=True, name=f"{self.node_id}-hello"),
            threading.Thread(target=self._liveness_loop, daemon=True, name=f"{self.node_id}-liveness"),
            threading.Thread(target=self._lsa_periodic_loop, daemon=True, name=f"{self.node_id}-lsa"),
        ]
        for t in self.threads:
            t.start()

        # Emitir LSA inicial
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
                client_sock, _ = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except Exception:
                if not self.running:
                    break

    def _handle_client(self, client_sock: socket.socket) -> None:
        with client_sock:
            while self.running:
                try:
                    packet = recv_packet(client_sock)
                    if packet is None:
                        break
                    self._handle_packet(packet)
                except Exception:
                    break

    def _handle_packet(self, packet: dict) -> None:
        p_type = packet.get("type")
        if p_type == "HELLO":
            self.process_hello(packet)
        elif p_type == "LSA":
            self.flood_lsa(packet, sender=packet.get("from"))
        elif "nodo_destino" in packet:
            dest = packet["nodo_destino"]
            orig = packet.get("nodo_origen", "?")
            if dest == self.node_id:
                print(f"\n[{self.node_id}] *** MENSAJE RECIBIDO ***")
                print(f"   De:      {orig}")
                print(f"   Mensaje: {packet.get('mensaje')}")
                print(f"{'─'*50}\n", flush=True)
            else:
                route_info = self.forward_data_packet(packet)
                next_hop = route_info["next_hop"]
                if next_hop:
                    ip, port = route_info["ip"], route_info["port"]
                    router_print(f"[{self.node_id}][FWD] Reenviando a {dest} vía {next_hop} ({ip}:{port})", flush=True)
                    threading.Thread(
                        target=self._send_to_address,
                        args=(ip, port, packet),
                        daemon=True,
                    ).start()
                else:
                    router_print(f"[{self.node_id}][FWD] Sin ruta para '{dest}'. Descartando.", flush=True)

    def _send_to_node(self, target_id: str, packet: dict) -> bool:
        addr = self.node_addresses.get(target_id)
        if not addr:
            return False
        return self._send_to_address(addr[0], addr[1], packet)

    def _send_to_address(self, ip: str, port: int, packet: dict) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(3.0)
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
                ok = self._send_to_node(neighbor_id, hello_msg)
                mark = "✓" if ok else "✗ (sin respuesta)"
                router_print(f"[{self.node_id}] HELLO -> {neighbor_id} {mark}", flush=True)
            time.sleep(self.hello_interval)

    def _liveness_loop(self) -> None:
        while self.running:
            time.sleep(1.0)
            now = time.time()
            lsa_to_flood = None
            with self.lock:
                changed = False
                for neighbor_id in list(self.neighbors.keys()):
                    last = self.neighbor_last_seen.get(neighbor_id)
                    if last is not None and (now - last) > self.dead_interval:
                        router_print(f"[{self.node_id}] VECINO CAIDO: {neighbor_id} (sin HELLO por > {self.dead_interval}s)", flush=True)
                        del self.neighbors[neighbor_id]
                        changed = True

                if changed:
                    self._update_self_lsa_state()
                    self._rebuild_topology_and_routes()
                    lsa_to_flood = self._build_lsa_nolock()

            if lsa_to_flood:
                self.flood_lsa(lsa_to_flood, sender=self.node_id)

    def _lsa_periodic_loop(self) -> None:
        while self.running:
            time.sleep(self.lsa_interval)
            lsa = self.build_lsa()  # Adquiere/libera lock internamente
            self.flood_lsa(lsa, sender=self.node_id)


def compute_shortest_paths(graph: Dict[str, Dict[str, int]], source: str) -> Dict[str, Tuple[str, int, List[str]]]:
    nodes = set(graph.keys())
    for neighbors in graph.values():
        nodes.update(neighbors.keys())

    distances = {node: float("inf") for node in nodes}
    distances[source] = 0
    previous: Dict[str, str] = {}
    pq = [(0, source)]

    while pq:
        current_cost, node = heapq.heappop(pq)
        if current_cost > distances[node]:
            continue
        for neighbor, weight in graph.get(node, {}).items():
            candidate = current_cost + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = node
                heapq.heappush(pq, (candidate, neighbor))

    paths = {}
    for node in nodes:
        if node == source or distances[node] == float("inf"):
            continue

        curr: Optional[str] = node
        path = []
        while curr is not None:
            path.append(curr)
            curr = previous.get(curr)
        path.reverse()

        next_hop = path[1] if len(path) > 1 else node
        paths[node] = (next_hop, int(distances[node]), path)

    return paths

