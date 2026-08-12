from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class TopologyConfig:
    def __init__(self, raw_data: Dict[str, Any]):
        self.nodes: Dict[str, Dict[str, Any]] = raw_data.get("nodes", {})

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
