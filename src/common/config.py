from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class TopologyConfig:
    def __init__(self, raw_data: Dict[str, Any]):
        if "nodes" in raw_data:
            self.nodes: Dict[str, Dict[str, Any]] = raw_data["nodes"]
        else:
            self.nodes: Dict[str, Dict[str, Any]] = self._parse_links_and_hosts(raw_data)

    def _parse_links_and_hosts(self, raw_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        nodes: Dict[str, Dict[str, Any]] = {}
        routers_info = raw_data.get("routers", {})

        # 1. Procesar enlaces (links) entre routers/nodos
        links = raw_data.get("links", [])
        for link in links:
            node_a = link.get("a")
            node_b = link.get("b")
            # Costo fijado en 1 según requerimiento
            cost = 1

            if not node_a or not node_b:
                continue

            for n_id in (node_a, node_b):
                if n_id not in nodes:
                    if n_id in routers_info and "port" in routers_info[n_id]:
                        port = int(routers_info[n_id]["port"])
                    else:
                        digits = "".join(filter(str.isdigit, n_id))
                        port = 5000 + int(digits) if digits else 5000

                    nodes[n_id] = {
                        "type": routers_info.get(n_id, {}).get("type", "router"),
                        "ip": routers_info.get(n_id, {}).get("ip", "127.0.0.1"),
                        "port": port,
                        "neighbors": {},
                    }

            nodes[node_a]["neighbors"][node_b] = cost
            nodes[node_b]["neighbors"][node_a] = cost

        # 2. Procesar end_hosts (ATM, Banco, etc.)
        end_hosts = raw_data.get("end_hosts", {})
        for host_id, host_info in end_hosts.items():
            h_type = host_info.get("type")
            if not h_type:
                if "ATM" in host_id.upper():
                    h_type = "atm"
                elif "BANK" in host_id.upper():
                    h_type = "bank"
                else:
                    h_type = "end_host"

            port = host_info.get("port", 5020 if h_type == "atm" else 5010)
            gateway = host_info.get("gateway")
            ip = host_info.get("ip", "127.0.0.1")

            neighbors = {}
            if gateway:
                neighbors[gateway] = 1

            nodes[host_id] = {
                "type": h_type,
                "ip": ip,
                "port": int(port),
                "gateway": gateway,
                "neighbors": neighbors,
                "owner": host_info.get("owner", ""),
            }

            if gateway:
                if gateway not in nodes:
                    digits = "".join(filter(str.isdigit, gateway))
                    gw_port = 5000 + int(digits) if digits else 5000
                    nodes[gateway] = {
                        "type": "router",
                        "ip": "127.0.0.1",
                        "port": gw_port,
                        "neighbors": {},
                    }
                nodes[gateway]["neighbors"][host_id] = 1

        return nodes

    @classmethod
    def load_from_file(cls, file_path: str) -> TopologyConfig:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo de topología no encontrado: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> Dict[str, int]:
        node_info = self.get_node(node_id)
        if not node_info:
            return {}
        return node_info.get("neighbors", {})

    def get_host_port(self, node_id: str) -> tuple[str, int]:
        node_info = self.get_node(node_id)
        if not node_info:
            raise KeyError(f"Nodo {node_id} no existe en la configuración")
        return node_info.get("ip", "127.0.0.1"), int(node_info.get("port", 5000))
