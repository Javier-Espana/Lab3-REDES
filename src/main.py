from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Añadir raíz del proyecto al path para importar network_settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.atm_client import ATMClient
from apps.bank_server import BankServer
from common.config import TopologyConfig
from common.hamming import decode_bits, encode_bits
from routers.router import LinkStateRouter

try:
    import network_settings as _net
    _NODE_IPS = _net.NODE_IPS
    _MODE_LABEL = _net.MODE_LABEL
except ImportError:
    _NODE_IPS = {}
    _MODE_LABEL = "Local (network_settings.py no encontrado)"


def _apply_network_settings(config: TopologyConfig) -> None:
    """Sobreescribe las IPs de la topología con las definidas en network_settings.py."""
    for node_id, info in config.nodes.items():
        if node_id in _NODE_IPS:
            info["ip"] = _NODE_IPS[node_id]


def run_single_node(node_id: str, config_path: str) -> None:
    print(f"[RED] Modo de conexión: {_MODE_LABEL}")
    config = TopologyConfig.load_from_file(config_path)
    _apply_network_settings(config)
    node_info = config.get_node(node_id)
    if not node_info:
        print(f"Error: El nodo {node_id} no se encuentra en {config_path}")
        sys.exit(1)

    node_type = node_info.get("type", "router")
    ip = node_info.get("ip", "127.0.0.1")
    port = int(node_info.get("port", 5000))

    # Construir mapa de direcciones de todos los nodos
    node_addresses = {nid: (info["ip"], int(info["port"])) for nid, info in config.nodes.items()}

    if node_type == "router":
        neighbors = node_info.get("neighbors", {})
        router = LinkStateRouter(
            node_id=node_id,
            neighbors=neighbors,
            host=ip,
            port=port,
            node_addresses=node_addresses,
        )
        print(f"Iniciando Router [{node_id}] en {ip}:{port}...")
        router.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print(f"Deteniendo Router [{node_id}]...")
            router.stop()

    elif node_type == "bank":
        gateway_id = node_info.get("gateway")
        gateway_addr = node_addresses.get(gateway_id) if gateway_id else None
        bank = BankServer(node_id=node_id, host=ip, port=port, gateway_addr=gateway_addr)
        print(f"Iniciando Banco [{node_id}] en {ip}:{port} (Gateway: {gateway_id} {gateway_addr})...")
        bank.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print(f"Deteniendo Banco [{node_id}]...")
            bank.stop()

    elif node_type == "atm":
        gateway_id = node_info.get("gateway")
        gateway_addr = node_addresses.get(gateway_id) if gateway_id else None
        bank_id = "BANK1"
        atm = ATMClient(node_id=node_id, bank_id=bank_id, host=ip, port=port, gateway_addr=gateway_addr)
        print(f"Iniciando Cajero ATM [{node_id}] en {ip}:{port} (Gateway: {gateway_id} {gateway_addr})...")
        atm.start()
        print("\n--- Menú Interactivo ATM ---")
        print("Comandos disponibles: login, withdraw <monto>, logout, exit")
        try:
            while True:
                cmd = input(f"{node_id}> ").strip().split()
                if not cmd:
                    continue
                action = cmd[0].lower()
                if action == "exit":
                    break
                elif action == "login":
                    card = input("Número de tarjeta (ej. 4111111111111111): ").strip()
                    pin = input("PIN (ej. 1234): ").strip()
                    res = atm.login(card, pin)
                    print("Respuesta:", res)
                elif action == "withdraw":
                    amt = float(cmd[1]) if len(cmd) > 1 else float(input("Monto a retirar: ").strip())
                    res = atm.withdraw(amt)
                    print("Respuesta:", res)
                elif action == "logout":
                    res = atm.logout()
                    print("Respuesta:", res)
                else:
                    print("Comando desconocido.")
        except KeyboardInterrupt:
            pass
        finally:
            atm.stop()


def run_demo(config_path: str) -> None:
    print("==================================================")
    print("  SIMULACIÓN COMPLETA - LABORATORIO 3 (ENRUTAMIENTO)")
    print(f"  Modo de conexión: {_MODE_LABEL}")
    print("==================================================")
    config = TopologyConfig.load_from_file(config_path)
    _apply_network_settings(config)
    node_addresses = {nid: (info["ip"], int(info["port"])) for nid, info in config.nodes.items()}

    routers: dict[str, LinkStateRouter] = {}
    bank_server: BankServer | None = None
    atm_client: ATMClient | None = None

    print("\n1. Levantando nodos en paralelo...")
    for node_id, info in config.nodes.items():
        ntype = info.get("type", "router")
        ip = info["ip"]
        port = int(info["port"])

        if ntype == "router":
            r = LinkStateRouter(
                node_id=node_id,
                neighbors=info.get("neighbors", {}),
                host=ip,
                port=port,
                node_addresses=node_addresses,
                hello_interval=1.0,
                lsa_interval=3.0,
            )
            r.start()
            routers[node_id] = r
        elif ntype == "bank":
            gw_id = info.get("gateway")
            gw_addr = node_addresses.get(gw_id) if gw_id else None
            bank_server = BankServer(node_id=node_id, host=ip, port=port, gateway_addr=gw_addr)
            bank_server.start()
        elif ntype == "atm":
            gw_id = info.get("gateway")
            gw_addr = node_addresses.get(gw_id) if gw_id else None
            atm_client = ATMClient(node_id=node_id, bank_id="BANK1", host=ip, port=port, gateway_addr=gw_addr)
            atm_client.start()

    print("\n2. Esperando a que el intercambio de HELLO y LSA estabilice las tablas de enrutamiento (5s)...")
    time.sleep(5.0)

    print("\n3. Muestra de Tablas de Enrutamiento CSV generadas:")
    output_dir = os.path.join(os.getcwd(), "output")
    for r_id in ["R1", "R6"]:
        csv_file = os.path.join(output_dir, f"{r_id}_nodo_tabla_enrutamiento.csv")
        print(f"\n--- Tabla de enrutamiento [{r_id}] ({csv_file}) ---")
        if os.path.exists(csv_file):
            with open(csv_file, "r", encoding="utf-8") as f:
                print(f.read().strip())

    print("\n4. Demostración de Capa de Detección/Corrección de Errores Hamming (7,4):")
    sample_pkt = {
        "nodo_origen": "ATM1",
        "nodo_destino": "BANK1",
        "mensaje": {"action": "withdraw", "data": {"amount": 100}},
    }
    sample_bits = "".join(format(ord(c), "08b") for c in json.dumps(sample_pkt))
    encoded = encode_bits(sample_bits)
    decoded = decode_bits(encoded)
    print(f"Paquete original (primeros 64 bits): {sample_bits[:64]}")
    print(f"Codificación Hamming 7,4 (primeros 112 bits): {encoded[:112]}")
    print(f"Decodificación sin errores (primeros 64 bits): {decoded[:64]}")
    assert sample_bits == decoded, "Hamming verification failed"
    print("-> Verificación Hamming (7,4) EXITOSA!")

    print("\n5. Demostración Transacción Bancaria End-to-End (ATM1 -> R1 -> ... -> R6 -> BANK1):")
    if atm_client:
        print("\n-> [Paso 1] Intentando Login en Banco con datos válidos...")
        res_login = atm_client.login("4111111111111111", "1234", timeout=5.0)
        print("   Respuesta del Banco:", res_login)

        print("\n-> [Paso 2] Intentando Retiro de $100.00...")
        res_withdraw = atm_client.withdraw(100.0, timeout=5.0)
        print("   Respuesta del Banco:", res_withdraw)

        print("\n-> [Paso 3] Intentando Logout...")
        res_logout = atm_client.logout(timeout=5.0)
        print("   Respuesta del Banco:", res_logout)

    print("\n6. Finalizando la simulación y cerrando sockets...")
    if atm_client:
        atm_client.stop()
    if bank_server:
        bank_server.stop()
    for r in routers.values():
        r.stop()
    print("==================================================")
    print("  SIMULACIÓN FINALIZADA CON ÉXITO")
    print("==================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 3 - Algoritmos de Enrutamiento Link State")
    parser.add_argument("--config", type=str, default="topology.json", help="Ruta al archivo topology.json")
    parser.add_argument("--node", type=str, default=None, help="ID del nodo a ejecutar individualmente (ej. R1, BANK1, ATM1)")
    parser.add_argument("--all", action="store_true", help="Ejecutar simulación completa de la topología")
    parser.add_argument("--demo", action="store_true", help="Ejecutar demostración automatizada")

    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        # Intentar ruta relativa desde directorio actual
        config_path = os.path.join(os.getcwd(), "topology.json")

    if args.node:
        run_single_node(args.node, config_path)
    else:
        run_demo(config_path)


if __name__ == "__main__":
    main()
