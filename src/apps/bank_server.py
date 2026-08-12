from __future__ import annotations

import socket
import threading
import time
from typing import Any, Dict, Optional, Tuple

from common.framing import recv_packet, send_packet


class BankServer:
    def __init__(
        self,
        node_id: str = "BANK1",
        host: str = "127.0.0.1",
        port: int = 5010,
        gateway_addr: Optional[Tuple[str, int]] = None,
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.gateway_addr = gateway_addr  # (gateway_ip, gateway_port)

        # Base de datos simulada de cuentas bancarias
        self.accounts = {
            "4111111111111111": {"pin": "1234", "balance": 500.00},
            "1234567890123456": {"pin": "0000", "balance": 1000.00},
        }
        self.sessions: Dict[str, str] = {}  # card -> session_status

        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.lock = threading.Lock()

    def start(self) -> None:
        """Inicia el servidor bancario y escucha peticiones en su puerto TCP."""
        if self.running:
            return
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)

        threading.Thread(target=self._server_loop, daemon=True, name=f"{self.node_id}-bank").start()

    def stop(self) -> None:
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
                packet = recv_packet(client_sock)
                if packet is None:
                    break
                response_packet = self.handle_packet(packet)
                if response_packet:
                    # Enviar respuesta vía gateway (puerta de enlace) o directamente si no hay gateway definido
                    if self.gateway_addr:
                        self._send_to_gateway(response_packet)
                    else:
                        send_packet(client_sock, response_packet)

    def handle_packet(self, packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        dest = packet.get("nodo_destino")
        if dest != self.node_id:
            return None

        origin = packet.get("nodo_origen")
        mensaje = packet.get("mensaje", {})
        action = mensaje.get("action")
        data = mensaje.get("data", {})

        response_msg = self._process_action(origin, action, data)
        return {
            "nodo_origen": self.node_id,
            "nodo_destino": origin,
            "mensaje": response_msg,
        }

    def _process_action(self, origin: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if action == "login":
                card = str(data.get("card"))
                pin = str(data.get("pin"))
                if card in self.accounts and self.accounts[card]["pin"] == pin:
                    self.sessions[origin] = card
                    return {"action": "login_ok", "data": {"message": "Authentication successful"}}
                return {"action": "login_denied", "data": {"message": "Invalid credentials"}}

            elif action == "withdraw":
                card = self.sessions.get(origin)
                if not card:
                    return {"action": "error", "data": {"message": "User not authenticated"}}

                amount = float(data.get("amount", 0))
                account = self.accounts[card]
                if amount <= 0:
                    return {"action": "error", "data": {"message": "Invalid withdrawal amount"}}

                if account["balance"] >= amount:
                    account["balance"] -= amount
                    return {
                        "action": "withdraw_ok",
                        "data": {"amount": amount, "balance": account["balance"]},
                    }
                return {"action": "error", "data": {"message": "Insufficient funds"}}

            elif action == "logout":
                if origin in self.sessions:
                    del self.sessions[origin]
                return {"action": "logout_ok", "data": {"message": "Logged out successfully"}}

            else:
                return {"action": "error", "data": {"message": f"Unknown action '{action}'"}}

    def _send_to_gateway(self, packet: Dict[str, Any]) -> bool:
        if not self.gateway_addr:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect(self.gateway_addr)
                send_packet(s, packet)
                return True
        except Exception as e:
            print(f"[{self.node_id}] Error al enviar respuesta a gateway {self.gateway_addr}: {e}")
            return False
