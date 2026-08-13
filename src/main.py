from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Añadir src/ al path
_SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(_SRC))

from apps.atm_client import ATMClient
from apps.bank_server import BankServer
from common.config import TopologyConfig
from common.hamming import decode_bits, encode_bits
from routers.router import LinkStateRouter

# ---------------------------------------------------------------------------
# Modo de conexión: se lee de src/network_settings.py
# El flag --local sobreescribe USE_TAILSCALE=False
# ---------------------------------------------------------------------------
try:
    import network_settings as _ns
    _USE_TAILSCALE = _ns.USE_TAILSCALE
except ImportError:
    _USE_TAILSCALE = False


def _load_config(config_path: str, local: bool) -> TopologyConfig:
    use_local_ips = local or not _USE_TAILSCALE
    return TopologyConfig.load_from_file(config_path, use_local_ips=use_local_ips)


def _resolve_config_path(given: str) -> str:
    p = os.path.abspath(given)
    if os.path.exists(p):
        return p
    # Buscar en el directorio de trabajo
    p2 = os.path.join(os.getcwd(), "topology.json")
    if os.path.exists(p2):
        return p2
    raise FileNotFoundError(f"No se encontró el archivo de topología: {given}")


# ---------------------------------------------------------------------------
# Modo: ejecutar un nodo individual
# ---------------------------------------------------------------------------
def _bind_host(local: bool) -> str:
    """En modo Tailscale se hace bind a 0.0.0.0 (todas las interfaces).
    En modo local se hace bind a 127.0.0.1."""
    return "127.0.0.1" if (local or not _USE_TAILSCALE) else "0.0.0.0"


def run_single_node(node_id: str, config_path: str, local: bool = False) -> None:
    config = _load_config(config_path, local)
    node_info = config.get_node(node_id)
    if not node_info:
        print(f"Error: El nodo '{node_id}' no existe en la topologia.")
        print(f"Nodos disponibles: {', '.join(config.nodes.keys())}")
        sys.exit(1)

    node_type = node_info.get("type", "router")
    advertised_ip = node_info.get("ip", "127.0.0.1")
    port = int(node_info.get("port", 5000))
    bind_ip = _bind_host(local)
    node_addresses = {nid: (info["ip"], int(info["port"])) for nid, info in config.nodes.items()}

    mode = "Local" if (local or not _USE_TAILSCALE) else "Tailscale"
    print(f"[{node_id}] Modo: {mode} | Bind: {bind_ip}:{port} | Advertised: {advertised_ip}:{port}")

    if node_type == "router":
        router = LinkStateRouter(
            node_id=node_id,
            neighbors=node_info.get("neighbors", {}),
            host=bind_ip,
            port=port,
            node_addresses=node_addresses,
        )
        print(f"Iniciando Router [{node_id}] en {bind_ip}:{port}...")
        router.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print(f"\nDeteniendo Router [{node_id}]...")
            router.stop()

    elif node_type == "bank":
        gw_id = node_info.get("gateway")
        gw_addr = node_addresses.get(gw_id) if gw_id else None
        bank = BankServer(node_id=node_id, host=bind_ip, port=port, gateway_addr=gw_addr)
        print(f"Iniciando Banco [{node_id}] en {bind_ip}:{port}...")
        bank.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print(f"\nDeteniendo Banco [{node_id}]...")
            bank.stop()

    elif node_type == "atm":
        gw_id = node_info.get("gateway")
        gw_addr = node_addresses.get(gw_id) if gw_id else None
        atm = ATMClient(node_id=node_id, bank_id="BANK1", host=bind_ip, port=port, gateway_addr=gw_addr)
        print(f"Iniciando Cajero [{node_id}] en {bind_ip}:{port}...")
        atm.start()
        _atm_cli(atm, node_id)
        atm.stop()


# ---------------------------------------------------------------------------
# Modo: ejecutar todos los nodos de un participante (owner)
# ---------------------------------------------------------------------------
def run_participant_nodes(participant_id: str, config_path: str, local: bool = False) -> None:
    config = _load_config(config_path, local)
    assigned = config.get_nodes_for_owner(participant_id)

    if not assigned:
        print(f"Error: No hay nodos asignados al propietario '{participant_id}'.")
        owners = sorted(set(info.get("owner", "") for info in config.nodes.values() if info.get("owner")))
        if owners:
            print(f"Propietarios disponibles: {', '.join(owners)}")
        sys.exit(1)

    mode = "Local" if (local or not _USE_TAILSCALE) else "Tailscale"
    print("=" * 50)
    print(f"  PROPIETARIO: {participant_id}  |  Modo: {mode}")
    print(f"  Nodos: {', '.join(assigned)}")
    print("=" * 50)

    node_addresses = {nid: (info["ip"], int(info["port"])) for nid, info in config.nodes.items()}
    bind_ip = _bind_host(local)

    routers: dict[str, LinkStateRouter] = {}
    banks: list[BankServer] = []
    atm_client: ATMClient | None = None

    # Routers primero
    for nid in assigned:
        info = config.nodes[nid]
        if info.get("type") == "router":
            r = LinkStateRouter(
                node_id=nid,
                neighbors=info.get("neighbors", {}),
                host=bind_ip,
                port=int(info["port"]),
                node_addresses=node_addresses,
            )
            print(f"Iniciando Router [{nid}] en {bind_ip}:{info['port']}...")
            r.start()
            routers[nid] = r

    # Bancos
    for nid in assigned:
        info = config.nodes[nid]
        if info.get("type") == "bank":
            gw_id = info.get("gateway")
            gw_addr = node_addresses.get(gw_id) if gw_id else None
            b = BankServer(node_id=nid, host=bind_ip, port=int(info["port"]), gateway_addr=gw_addr)
            print(f"Iniciando Banco [{nid}] en {bind_ip}:{info['port']}...")
            b.start()
            banks.append(b)

    # Cajero ATM
    for nid in assigned:
        info = config.nodes[nid]
        if info.get("type") == "atm":
            gw_id = info.get("gateway")
            gw_addr = node_addresses.get(gw_id) if gw_id else None
            atm_client = ATMClient(node_id=nid, bank_id="BANK1", host=bind_ip, port=int(info["port"]), gateway_addr=gw_addr)
            print(f"Iniciando Cajero [{nid}] en {bind_ip}:{info['port']}...")
            atm_client.start()

    print("\nTodos tus nodos estan corriendo.")

    if atm_client:
        _atm_cli(atm_client, atm_client.node_id)
        print("\nDeteniendo nodos...")
        atm_client.stop()
        for b in banks:
            b.stop()
        for r in routers.values():
            r.stop()
    else:
        print("Presiona Ctrl+C para detener.\n")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nDeteniendo nodos...")
            for b in banks:
                b.stop()
            for r in routers.values():
                r.stop()


# ---------------------------------------------------------------------------
# Modo: demo completa (todos los nodos en local)
# ---------------------------------------------------------------------------
def run_demo(config_path: str) -> None:
    print("=" * 50)
    print("  SIMULACION COMPLETA - LABORATORIO 3")
    print("=" * 50)
    config = _load_config(config_path, local=True)
    node_addresses = {nid: (info["ip"], int(info["port"])) for nid, info in config.nodes.items()}
    bind_ip = "127.0.0.1"

    routers: dict[str, LinkStateRouter] = {}
    bank_server: BankServer | None = None
    atm_client: ATMClient | None = None

    print("\n1. Levantando nodos...")
    for node_id, info in config.nodes.items():
        ntype = info.get("type", "router")
        port = int(info["port"])

        if ntype == "router":
            r = LinkStateRouter(
                node_id=node_id,
                neighbors=info.get("neighbors", {}),
                host=bind_ip,
                port=port,
                node_addresses=node_addresses,
                hello_interval=1.0,
                lsa_interval=3.0,
            )
            r.start()
            routers[node_id] = r
        elif ntype == "bank":
            gw_addr = node_addresses.get(info.get("gateway")) if info.get("gateway") else None
            bank_server = BankServer(node_id=node_id, host=bind_ip, port=port, gateway_addr=gw_addr)
            bank_server.start()
        elif ntype == "atm":
            gw_addr = node_addresses.get(info.get("gateway")) if info.get("gateway") else None
            atm_client = ATMClient(node_id=node_id, bank_id="BANK1", host=bind_ip, port=port, gateway_addr=gw_addr)
            atm_client.start()

    print("\n2. Esperando convergencia de tablas de enrutamiento (5s)...")
    time.sleep(5.0)

    print("\n3. Tablas de Enrutamiento:")
    output_dir = os.path.join(os.getcwd(), "output")
    for r_id in ["R1", "R4", "R6"]:
        csv_file = os.path.join(output_dir, f"{r_id}_nodo_tabla_enrutamiento.csv")
        print(f"\n--- [{r_id}] ---")
        if os.path.exists(csv_file):
            with open(csv_file, "r", encoding="utf-8") as f:
                print(f.read().strip())
        else:
            print("(tabla aun no generada)")

    print("\n4. Verificacion Hamming (7,4):")
    sample = {"nodo_origen": "ATM1", "nodo_destino": "BANK1", "mensaje": {"action": "withdraw", "data": {"amount": 100}}}
    bits = "".join(format(ord(c), "08b") for c in json.dumps(sample))
    encoded = encode_bits(bits)
    decoded = decode_bits(encoded)
    assert bits == decoded, "Hamming round-trip failed"
    print("-> Verificacion Hamming (7,4) EXITOSA")

    print("\n5. Transaccion Bancaria End-to-End (ATM1 -> ... -> BANK1):")
    if atm_client:
        print("\n-> Login...")
        res = atm_client.login("4111111111111111", "1234", timeout=5.0)
        print("   Respuesta:", res)

        print("\n-> Retiro $100...")
        res = atm_client.withdraw(100.0, timeout=5.0)
        print("   Respuesta:", res)

        print("\n-> Logout...")
        res = atm_client.logout(timeout=5.0)
        print("   Respuesta:", res)

    print("\n6. Cerrando nodos...")
    if atm_client:
        atm_client.stop()
    if bank_server:
        bank_server.stop()
    for r in routers.values():
        r.stop()
    print("=" * 50)
    print("  SIMULACION FINALIZADA")
    print("=" * 50)


# ---------------------------------------------------------------------------
# CLI interactivo del cajero ATM
# ---------------------------------------------------------------------------
def _atm_cli(atm: ATMClient, node_id: str) -> None:
    print("\n--- Menu ATM ---")
    print("Comandos: login, withdraw <monto>, logout, exit\n")
    try:
        while True:
            cmd = input(f"{node_id}> ").strip().split()
            if not cmd:
                continue
            action = cmd[0].lower()
            if action == "exit":
                break
            elif action == "login":
                card = input("Tarjeta: ").strip()
                pin = input("PIN: ").strip()
                print("Respuesta:", atm.login(card, pin))
            elif action == "withdraw":
                amt = float(cmd[1]) if len(cmd) > 1 else float(input("Monto: ").strip())
                print("Respuesta:", atm.withdraw(amt))
            elif action == "logout":
                print("Respuesta:", atm.logout())
            else:
                print("Comando desconocido.")
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 3 - Enrutamiento Link State")
    parser.add_argument("--config", default="topology.json", help="Ruta al topology.json")
    parser.add_argument("--node", default=None, help="Nodo individual a ejecutar (ej: R1, BANK1, ATM1)")
    parser.add_argument(
        "--participant", "--person", "-p",
        default=None,
        help="Ejecutar todos los nodos de un propietario (ej: P1, P2)",
    )
    parser.add_argument("--local", action="store_true", help="Forzar IPs locales (127.0.0.1)")
    parser.add_argument("--demo", action="store_true", help="Ejecutar simulacion automatizada completa")

    args = parser.parse_args()

    try:
        config_path = _resolve_config_path(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.participant:
        run_participant_nodes(args.participant, config_path, local=args.local)
    elif args.node:
        run_single_node(args.node, config_path, local=args.local)
    else:
        run_demo(config_path)


if __name__ == "__main__":
    main()
