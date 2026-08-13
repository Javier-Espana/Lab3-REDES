# =============================================================================
#  CONFIGURACIÓN DE RED - Lab3 REDES
# =============================================================================
#  Cambia USE_TAILSCALE a True para conectar vía Tailscale,
#  o a False para conectar localmente (localhost).
# =============================================================================

USE_TAILSCALE = False   # <-- ÚNICA LÍNEA QUE HAY QUE CAMBIAR

# -----------------------------------------------------------------------------
# IPs de Tailscale — una variable por persona/máquina
# Cada quien solo edita SU línea con la IP que aparece en Tailscale (100.x.x.x)
# -----------------------------------------------------------------------------
IP_JAVIER  = "100.x.x.1"   # <-- Javier: pon aquí tu IP de Tailscale
IP_ROBERTO = "100.x.x.2"   # <-- Roberto: pon aquí tu IP de Tailscale

# (Si algún día se unen más pares, agregar sus IPs aquí)
# IP_PERSONA3 = "100.x.x.3"

# -----------------------------------------------------------------------------
# Asignación de nodos a máquinas
# Si corres varios nodos en tu máquina, todos comparten tu misma IP.
# Solo cambia el valor si un nodo se mueve a otra máquina.
# -----------------------------------------------------------------------------
TAILSCALE_IPS = {
    "ATM1":  IP_JAVIER,    # Javier corre ATM1
    "R1":    IP_JAVIER,    # Javier corre R1
    "R2":    IP_JAVIER,    # Javier corre R2
    "R3":    IP_ROBERTO,   # Roberto corre R3
    "R4":    IP_ROBERTO,   # Roberto corre R4
    "R5":    IP_ROBERTO,   # Roberto corre R5
    "R6":    IP_ROBERTO,   # Roberto corre R6
    "BANK1": IP_ROBERTO,   # Roberto corre BANK1
}

# -----------------------------------------------------------------------------
# IPs locales (no cambiar salvo que uses una interfaz distinta a loopback)
# -----------------------------------------------------------------------------
LOCAL_IPS = {
    "ATM1":  "127.0.0.1",
    "R1":    "127.0.0.1",
    "R2":    "127.0.0.1",
    "R3":    "127.0.0.1",
    "R4":    "127.0.0.1",
    "R5":    "127.0.0.1",
    "R6":    "127.0.0.1",
    "BANK1": "127.0.0.1",
}

# =============================================================================
# (No modificar a partir de aquí — lógica automática)
# =============================================================================
NODE_IPS: dict = TAILSCALE_IPS if USE_TAILSCALE else LOCAL_IPS

MODE_LABEL = "Tailscale" if USE_TAILSCALE else "Local"
