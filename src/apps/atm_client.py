from __future__ import annotations

import socket
import threading
import time
from typing import Any, Dict, Optional, Tuple

from common.framing import recv_packet, send_packet


class ATMClient:
    def __init__(
        self,
        node_id: str = "ATM1",
        bank_id: str = "BANK1",
        host: str = "127.0.0.1",
        port: int = 5020,
        gateway_addr: Optional[Tuple[str, int]] = None,
    ):
        self.node_id = node_id
        self.bank_id = bank_id
        self.host = host
        self.port = port
        self.gateway_addr = gateway_addr  # (gateway_ip, gateway_port)

        self.running = False
        self.server_socket: Optional[socket.socket] = None

        self.active_event: Optional[threading.Event] = None
        self.latest_response: Optional[Dict[str, Any]] = None
        self.lock = threading.Lock()

    def start(self) -> None:
        """Inicia el cliente ATM como escucha TCP para respuestas recibidas desde el router."""
        if self.running:
            return
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)

        threading.Thread(target=self._server_loop, daemon=True, name=f"{self.node_id}-atm").start()

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
                threading.Thread(target=self._handle_incoming, args=(client_sock,), daemon=True).start()
            except Exception:
                if not self.running:
                    break

    def _handle_incoming(self, client_sock: socket.socket) -> None:
        with client_sock:
            while self.running:
                packet = recv_packet(client_sock)
                if packet is None:
                    break
                if packet.get("nodo_destino") == self.node_id:
                    mensaje = packet.get("mensaje", {})
                    with self.lock:
                        self.latest_response = mensaje
                        if self.active_event:
                            self.active_event.set()

    def send_request(self, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Envía una petición al Banco a través de la puerta de enlace router y espera la respuesta."""
        if not self.gateway_addr:
            raise RuntimeError("No se ha configurado la dirección de la puerta de enlace (gateway_addr)")

        packet = {
            "nodo_origen": self.node_id,
            "nodo_destino": self.bank_id,
            "mensaje": {"action": action, "data": data},
        }

        event = threading.Event()
        with self.lock:
            self.active_event = event
            self.latest_response = None

        # Enviar paquete por el socket de la puerta de enlace
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect(self.gateway_addr)
                send_packet(s, packet)
                try:
                    s.shutdown(socket.SHUT_WR)
                except Exception:
                    pass
                time.sleep(0.01)
        except Exception as e:
            print(f"[{self.node_id}] Error enviando paquete a gateway {self.gateway_addr}: {e}")
            with self.lock:
                self.active_event = None
            return None

        # Esperar respuesta
        got_response = event.wait(timeout=timeout)
        with self.lock:
            self.active_event = None
            if got_response:
                res = self.latest_response
                self.latest_response = None
                return res
            return None

    def login(self, card: str, pin: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        return self.send_request("login", {"card": card, "pin": pin}, timeout=timeout)

    def withdraw(self, amount: float, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        return self.send_request("withdraw", {"amount": amount}, timeout=timeout)

    def logout(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        return self.send_request("logout", {}, timeout=timeout)
