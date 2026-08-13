# =============================================================================
#  CONFIGURACIÓN DE RED - Lab3 REDES
# =============================================================================
#  Cambia USE_TAILSCALE a True para conectar vía Tailscale,
#  o a False para conectar localmente (localhost).
# =============================================================================

USE_TAILSCALE = False   # <-- ÚNICA LÍNEA QUE HAY QUE CAMBIAR

# =============================================================================
# PASO 1: Define los participantes y su IP de Tailscale
# -----------------------------------------------------------------------------
# Descomenta o agrega líneas según cuántos se conecten (mínimo 2, máximo 6).
# La IP la encuentras en la app de Tailscale o corriendo: tailscale ip -4
# =============================================================================
PARTICIPANTES = {
    "P1": "100.x.x.1",   # <-- P1: reemplaza con tu IP de Tailscale
    "P2": "100.x.x.2",   # <-- P2: reemplaza con tu IP de Tailscale
    # "P3": "100.x.x.3", # <-- Descomentar si se une una 3ra persona
    # "P4": "100.x.x.4", # <-- Descomentar si se une una 4ta persona
    # "P5": "100.x.x.5", # <-- Descomentar si se une una 5ta persona
    # "P6": "100.x.x.6", # <-- Descomentar si se une una 6ta persona
}

# =============================================================================
# PASO 2: Asigna qué nodos corre cada persona
# -----------------------------------------------------------------------------
# Cambia el valor (nombre del participante) según quién tenga cada nodo.
# Si alguien se une, redistribuye los nodos aquí.
# =============================================================================
NODO_A_PARTICIPANTE = {
    "ATM1":  "P1",
    "R1":    "P1",
    "R2":    "P1",
    "R3":    "P2",
    "R4":    "P2",
    "R5":    "P2",
    "R6":    "P2",
    "BANK1": "P2",
}

# =============================================================================
# IPs locales (no cambiar)
# =============================================================================
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

# Valida que todos los nodos asignados tengan un participante registrado
for _nodo, _persona in NODO_A_PARTICIPANTE.items():
    if _persona not in PARTICIPANTES:
        raise ValueError(
            f"[network_settings] El nodo '{_nodo}' está asignado a '{_persona}', "
            f"pero '{_persona}' no está en PARTICIPANTES. "
            f"Agrégalo o corrige el nombre."
        )

# Construye el mapa nodo -> IP de Tailscale automáticamente
TAILSCALE_IPS = {
    nodo: PARTICIPANTES[persona]
    for nodo, persona in NODO_A_PARTICIPANTE.items()
}

NODE_IPS: dict = TAILSCALE_IPS if USE_TAILSCALE else LOCAL_IPS

MODE_LABEL = "Tailscale" if USE_TAILSCALE else "Local"
