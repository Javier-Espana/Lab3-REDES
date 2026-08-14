from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple


class TopologyConfig:
    def __init__(self, raw_data: Dict[str, Any], use_local_ips: bool = False):
        self.raw_data = raw_data
        self.machines: Dict[str, str] = raw_data.get("machines", {})
        self.nodes: Dict[str, Dict[str, Any]] = {}

        if "links" in raw_data or "machines" in raw_data or "nodes" in raw_data:
            self._parse_mesh_format(use_local_ips)
        else:
            self._parse_legacy_format()

    @classmethod
    def load_from_file(cls, file_path: str, use_local_ips: bool = False) -> TopologyConfig:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo de topología no encontrado: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data, use_local_ips=use_local_ips)

    def _resolve_machine_ip(self, owner: str) -> str:
        owner_clean = owner.strip().upper()
        for k, v in self.machines.items():
            if k.strip().upper() == owner_clean:
                return v
        return "127.0.0.1"

    def _parse_mesh_format(self, use_local_ips: bool) -> None:
        # 1. Parse routers
        for node_id, info in self.raw_data.get("nodes", {}).items():
            owner = info.get("owner", "P1")
            ip = "127.0.0.1" if use_local_ips else self._resolve_machine_ip(owner)
            self.nodes[node_id] = {
                "type": info.get("type", "router"),
                "owner": owner,
                "ip": ip,
                "port": int(info.get("port", 5000)),
                "neighbors": {},
            }

        # 2. Parse links between routers
        for link in self.raw_data.get("links", []):
            a = link.get("a")
            b = link.get("b")
            cost = int(link.get("cost", 1))
            if a in self.nodes:
                self.nodes[a]["neighbors"][b] = cost
            if b in self.nodes:
                self.nodes[b]["neighbors"][a] = cost

        # 3. Parse end_hosts (ATM, BANK)
        for host_id, info in self.raw_data.get("end_hosts", {}).items():
            owner = info.get("owner", "P1")
            gateway = info.get("gateway")
            cost = int(info.get("cost", 1))
            ip = "127.0.0.1" if use_local_ips else self._resolve_machine_ip(owner)
            ntype = info.get("type", "atm" if host_id.upper().startswith("ATM") else "bank")

            self.nodes[host_id] = {
                "type": ntype,
                "owner": owner,
                "ip": ip,
                "port": int(info.get("port", 6000)),
                "gateway": gateway,
                "neighbors": {gateway: cost} if gateway else {},
            }
            if gateway and gateway in self.nodes:
                self.nodes[gateway]["neighbors"][host_id] = cost

    def _parse_legacy_format(self) -> None:
        self.nodes = self.raw_data.get("nodes", {})

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        target = node_id.strip().upper()
        for k, v in self.nodes.items():
            if k.strip().upper() == target:
                return v
        return None

    def get_neighbors(self, node_id: str) -> Dict[str, int]:
        node_info = self.get_node(node_id)
        if not node_info:
            return {}
        return node_info.get("neighbors", {})

    def get_host_port(self, node_id: str) -> Tuple[str, int]:
        node_info = self.get_node(node_id)
        if not node_info:
            raise KeyError(f"Nodo {node_id} no existe en la configuración")
        return node_info.get("ip", "127.0.0.1"), int(node_info.get("port", 5000))

    def get_nodes_for_owner(self, owner_name: str) -> List[str]:
        target = owner_name.strip().upper()
        return [
            nid for nid, info in self.nodes.items()
            if info.get("owner", "").strip().upper() == target
        ]

