# Laboratorio 3 - Protocolos de Enrutamiento

Universidad del Valle de Guatemala  
CC3084 - Redes - Semestre II 2026

## Integrantes
- Javier España #23361
- Roberto Barreda #23354

---

## Objetivo del proyecto
Este repositorio implementa un sistema de enrutamiento distribuido con el protocolo Link-State (LSA) y cálculo de rutas con Dijkstra. Incluye:
- Router con intercambio de paquetes HELLO y LSA.
- Cálculo y exportación de tablas de enrutamiento en CSV.
- Detección y corrección de errores con Hamming (7,4).
- Simulación de transacción bancaria ATM → Router(es) → Banco end-to-end.
- Soporte para ejecutar cada nodo en **máquinas distintas** conectadas vía **Tailscale**.

---

## Estructura del proyecto

```
Lab3-REDES/
├── network_settings.py      ← ARCHIVO DE CONFIGURACIÓN DE RED (editar aquí)
├── topology.json            ← Topología de nodos (puertos y vecinos)
├── src/
│   ├── main.py              ← Punto de entrada principal
│   ├── common/
│   │   ├── config.py        ← Carga de topología
│   │   ├── framing.py       ← Serialización de paquetes
│   │   └── hamming.py       ← Codificación/decodificación Hamming (7,4)
│   ├── routers/
│   │   └── router.py        ← Lógica del router Link-State
│   └── apps/
│       ├── atm_client.py    ← Cliente ATM
│       └── bank_server.py   ← Servidor Bancario
├── tests/
│   └── test_routing.py      ← Pruebas de Dijkstra y Hamming
└── output/                  ← Tablas de enrutamiento CSV generadas
```

---

## Requisitos

- Python **3.10** o superior.
- (Para red distribuida) **Tailscale** instalado en cada máquina.

---

## Ejecución local (una sola máquina)

Asegúrate de que `network_settings.py` tenga:

```python
USE_TAILSCALE = False
```

### Demostración automática completa

```bash
python src/main.py --demo
```

### Ejecutar un nodo individual

```bash
# Iniciar un router
python src/main.py --node R1

# Iniciar el banco
python src/main.py --node BANK1

# Iniciar el cajero ATM
python src/main.py --node ATM1
```

### Pruebas

```bash
pytest -q
```

---

## Ejecución distribuida con Tailscale

Esta es la guía para que cada integrante del equipo corra uno o más nodos en su propia máquina y se comuniquen entre sí a través de Tailscale.

### Paso 1 — Instalar Tailscale en cada máquina

1. Ir a [https://tailscale.com/download](https://tailscale.com/download) y descargar el instalador para tu sistema operativo.
2. Iniciar sesión con una cuenta de Google, GitHub, o Microsoft. **Todos los integrantes deben usar la misma cuenta** (o estar en la misma red Tailscale / "tailnet").
3. Una vez conectado, Tailscale asignará una IP privada de la forma `100.x.x.x` a cada máquina.

### Paso 2 — Encontrar tu IP de Tailscale

Puedes ver tu IP de Tailscale de tres formas:

- **En la aplicación Tailscale**: clic en el ícono de la bandeja del sistema → aparece tu IP.
- **En el panel web**: [https://login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines)
- **Por terminal**:
  ```bash
  # Windows (PowerShell)
  tailscale ip -4

  # Linux / macOS
  tailscale ip -4
  ```

### Paso 3 — Editar `network_settings.py`

Abre `network_settings.py` en la **raíz del proyecto**. El archivo tiene **dos secciones** que editar:

**1. Activa el modo Tailscale:**
```python
USE_TAILSCALE = True   # ← cambiar de False a True
```

**2. Agrega a cada participante numerado (P1, P2, ...) con su IP de Tailscale:**

Descomenta las líneas de los participantes que se vayan a conectar y asigna la IP real de cada uno:

```python
PARTICIPANTES = {
    "P1": "100.64.0.1",   # ← IP de Tailscale del participante 1
    "P2": "100.64.0.2",   # ← IP de Tailscale del participante 2
    # "P3": "100.64.0.3", # ← descomentar si se une un 3er participante
    # "P4": "100.64.0.4",
    # "P5": "100.64.0.5",
    # "P6": "100.64.0.6",
}
```

> **Cómo saber tu IP:** abre una terminal y ejecuta `tailscale ip -4`, o mírala en la app de Tailscale en la bandeja del sistema.

**3. Asigna qué nodos corre cada participante:**

```python
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
```

Las IPs se construyen automáticamente a partir de estas dos secciones. Si una clave en `NODO_A_PARTICIPANTE` no existe en `PARTICIPANTES`, el programa lanza un error claro al arrancar.

### Paso 4 — Coordinar quién corre qué nodo

Distribuye los nodos entre los participantes según cuántos haya. Ejemplos:

**Con 2 participantes (P1, P2):**

| Participante | Nodos                              |
|--------------|------------------------------------|
| P1           | `ATM1`, `R1`, `R2`                 |
| P2           | `R3`, `R4`, `R5`, `R6`, `BANK1`   |

**Con 3 participantes (P1, P2, P3):**

| Participante | Nodos                 |
|--------------|-----------------------|
| P1           | `ATM1`, `R1`          |
| P2           | `R2`, `R3`, `R4`      |
| P3           | `R5`, `R6`, `BANK1`   |

**Con 6 participantes (P1 a P6):**

| Participante | Nodos        |
|--------------|--------------|
| P1           | `ATM1`, `R1` |
| P2           | `R2`         |
| P3           | `R3`         |
| P4           | `R4`         |
| P5           | `R5`, `R6`   |
| P6           | `BANK1`      |

> **Nota:** No importa cuántos nodos corra cada participante. Lo importante es que la clave en `NODO_A_PARTICIPANTE` (ej. `"P1"`) coincida exactamente con la clave en `PARTICIPANTES`.

### Paso 5 — Ejecutar cada nodo en su máquina

Cada persona abre una terminal **por nodo** y ejecuta:

```bash
# terminal 1
python src/main.py --node ATM1

# terminal 2
python src/main.py --node R1

# terminal 3
python src/main.py --node R2

# terminal 1
python src/main.py --node R3

# ... y así sucesivamente
```

> **Nota:** Los routers deben levantarse **antes** que el ATM y el Banco para que el intercambio HELLO/LSA estabilice las tablas de enrutamiento.

### Paso 6 — Verificar la conexión

Cuando los nodos arranquen, verás en consola:

```
[RED] Modo de conexión: Tailscale
Iniciando Router [R1] en 100.x.x.1:5001...
```

Si ves `Local` en lugar de `Tailscale`, revisa que `USE_TAILSCALE = True` en `network_settings.py`.

### Solución de problemas comunes

| Problema | Solución |
|----------|----------|
| `Connection refused` al conectar | Verificar que el nodo destino ya está corriendo y que la IP en `TAILSCALE_IPS` es correcta. |
| Los nodos no se ven entre sí | Asegurarse de que ambas máquinas aparecen en [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) con estado "Connected". |
| `Address already in use` | Otro proceso ocupa el puerto. Cambiar el puerto en `topology.json` o cerrar el proceso anterior. |
| Firewall bloqueando | Tailscale normalmente pasa firewalls automáticamente. Si no, añadir excepción para los puertos 5001–5020 en el firewall de Windows/Linux. |

---

## Notas sobre el protocolo

- Todos los paquetes siguen el formato JSON: `{nodo_origen, nodo_destino, mensaje}`.
- Los routers intercambian paquetes `HELLO` para descubrir vecinos y `LSA` para propagar el estado del enlace.
- Las rutas se calculan con el algoritmo de Dijkstra sobre el grafo de la red.
- Cada paquete de datos se codifica con **Hamming (7,4)** para detección y corrección de errores de 1 bit.
- Las tablas de enrutamiento se exportan automáticamente a `output/<nodo>_nodo_tabla_enrutamiento.csv`.
