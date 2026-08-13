# Laboratorio 3 - Protocolos de Enrutamiento

Universidad del Valle de Guatemala  
CC3084 - Redes - Semestre II 2026

## Integrantes
- Javier Espana #23361
- Roberto Barreda #23354

---

## Objetivo del proyecto
Este repositorio implementa un sistema de enrutamiento distribuido con el protocolo Link-State (LSA) y calculo de rutas con Dijkstra. Incluye:
- Router con intercambio de paquetes HELLO y LSA.
- Calculo y exportacion de tablas de enrutamiento en CSV.
- Deteccion y correccion de errores con Hamming (7,4).
- Simulacion de transaccion bancaria ATM -> Router(es) -> Banco end-to-end.
- Soporte para ejecutar cada nodo en **maquinas distintas** conectadas via **Tailscale**.

---

## Estructura del proyecto

```
Lab3-REDES/
├── topology.json            <- FUENTE UNICA DE VERDAD (IPs, nodos, enlaces)
├── src/
│   ├── main.py              <- Punto de entrada principal
│   ├── network_settings.py  <- Solo controla USE_TAILSCALE = True/False
│   ├── common/
│   │   ├── config.py        <- Carga y parseo de topology.json
│   │   ├── framing.py       <- Serializacion de paquetes TCP
│   │   └── hamming.py       <- Codificacion/decodificacion Hamming (7,4)
│   ├── routers/
│   │   └── router.py        <- Logica del router Link-State
│   └── apps/
│       ├── atm_client.py    <- Cliente ATM
│       └── bank_server.py   <- Servidor Bancario
├── tests/
│   └── test_routing.py      <- Pruebas unitarias
└── output/                  <- Tablas de enrutamiento CSV generadas
```

---

## Requisitos

- Python **3.10** o superior.
- (Para red distribuida) **Tailscale** instalado en cada maquina.

---

## Configuracion: topology.json

Toda la configuracion de la red se define en un solo archivo: **`topology.json`**.

Este archivo contiene:
- **machines**: IP de Tailscale de cada participante (P1, P2, ...).
- **nodes**: routers de la red, cada uno con su propietario (`owner`) y puerto.
- **links**: enlaces entre routers con su costo.
- **end_hosts**: nodos terminales (ATM, Banco) con su propietario, puerto y gateway.

### Ejemplo de topology.json

```json
{
  "machines": {
    "P1": "100.93.223.104",
    "P2": "100.64.209.42"
  },
  "nodes": {
    "R1": { "owner": "P1", "port": 5001 },
    "R2": { "owner": "P1", "port": 5002 },
    "R3": { "owner": "P1", "port": 5003 },
    "R4": { "owner": "P2", "port": 5004 },
    "R5": { "owner": "P2", "port": 5005 },
    "R6": { "owner": "P2", "port": 5006 }
  },
  "links": [
    { "a": "R1", "b": "R2", "cost": 1 },
    { "a": "R2", "b": "R3", "cost": 2 },
    { "a": "R3", "b": "R4", "cost": 1 },
    { "a": "R4", "b": "R5", "cost": 3 },
    { "a": "R5", "b": "R6", "cost": 1 },
    { "a": "R6", "b": "R1", "cost": 4 },
    { "a": "R2", "b": "R5", "cost": 5 }
  ],
  "end_hosts": {
    "ATM1": { "owner": "P1", "port": 5020, "gateway": "R1", "cost": 1 },
    "BANK1": { "owner": "P2", "port": 5010, "gateway": "R4", "cost": 1 }
  }
}
```

Para modificar la red solo hay que editar este archivo:
- Cambiar IPs de participantes en `machines`.
- Agregar/quitar routers en `nodes`.
- Cambiar enlaces y costos en `links`.
- Reasignar propietarios cambiando el campo `owner`.

---

## Ejecucion local (una sola maquina)

Asegurate de que `src/network_settings.py` tenga:

```python
USE_TAILSCALE = False
```

O usa el flag `--local`:

### Demostracion automatica completa

```bash
python src/main.py --demo
# Equivalente con flag local:
python src/main.py --demo --local
```

### Ejecutar todos los nodos de tu grupo

```bash
# Si eres P1 (ejecuta ATM1, R1, R2, R3 juntos):
python src/main.py --participant P1 --local

# O usando el alias -p:
python src/main.py -p P1 --local
```

### Ejecutar un nodo individual

```bash
python src/main.py --node R1 --local
python src/main.py --node BANK1 --local
python src/main.py --node ATM1 --local
```

### Pruebas unitarias

```bash
python -m unittest discover tests
```

---

## Ejecucion distribuida con Tailscale

Guia para que cada integrante corra sus nodos en su propia maquina.

### Paso 1 -- Instalar Tailscale

1. Ir a [https://tailscale.com/download](https://tailscale.com/download).
2. Iniciar sesion. **Todos los integrantes deben estar en la misma red Tailscale**.
3. Tailscale asignara una IP `100.x.x.x` a cada maquina.

### Paso 2 -- Encontrar tu IP de Tailscale

```bash
tailscale ip -4
```

O mira la app de Tailscale / [panel web](https://login.tailscale.com/admin/machines).

### Paso 3 -- Editar topology.json

1. En la seccion `machines`, coloca la IP real de cada participante:

```json
"machines": {
    "P1": "100.93.223.104",
    "P2": "100.64.209.42"
}
```

2. En `nodes` y `end_hosts`, asigna el `owner` correcto a cada nodo segun quien lo va a ejecutar.

3. Asegurate de que `src/network_settings.py` tenga:

```python
USE_TAILSCALE = True
```

### Paso 4 -- Distribuir nodos

Ejemplo con 2 participantes:

| Participante | Nodos                    |
|--------------|--------------------------|
| P1           | ATM1, R1, R2, R3         |
| P2           | R4, R5, R6, BANK1        |

Ejemplo con 3 participantes:

| Participante | Nodos              |
|--------------|--------------------|
| P1           | ATM1, R1           |
| P2           | R2, R3, R4         |
| P3           | R5, R6, BANK1      |

### Paso 5 -- Ejecutar

Cada persona corre un solo comando:

```bash
# Persona 1:
python src/main.py -p P1

# Persona 2:
python src/main.py -p P2
```

Este comando levanta automaticamente todos los nodos asignados a ese propietario en `topology.json`. Si tu grupo incluye el cajero ATM1, se abre el menu interactivo.

### Paso 6 -- Verificar la conexion

Al arrancar veras en consola:

```
==================================================
  PROPIETARIO: P1  |  Modo: Tailscale
  Nodos: R1, R2, R3, ATM1
==================================================
Iniciando Router [R1] en 100.93.223.104:5001...
Iniciando Router [R2] en 100.93.223.104:5002...
...
```

Si ves `Modo: Local` en lugar de `Tailscale`, revisa que `USE_TAILSCALE = True` en `src/network_settings.py`.

### Solucion de problemas comunes

| Problema | Solucion |
|----------|----------|
| `Connection refused` | Verificar que el nodo destino ya esta corriendo y que la IP en `topology.json` es correcta. |
| Los nodos no se ven entre si | Verificar que ambas maquinas aparecen como "Connected" en el panel de Tailscale. |
| `Address already in use` | Otro proceso ocupa el puerto. Cerrar el proceso anterior o cambiar el puerto en `topology.json`. |
| Firewall bloqueando | Tailscale normalmente pasa firewalls. Si no, agregar excepcion para los puertos 5001-5020. |

---

## Notas sobre el protocolo

- Todos los paquetes siguen el formato JSON: `{nodo_origen, nodo_destino, mensaje}`.
- Los routers intercambian paquetes `HELLO` para descubrir vecinos y `LSA` para propagar el estado del enlace.
- Las rutas se calculan con el algoritmo de Dijkstra sobre el grafo de la red.
- Cada paquete de datos se codifica con **Hamming (7,4)** para deteccion y correccion de errores de 1 bit.
- Las tablas de enrutamiento se exportan automaticamente a `output/<nodo>_nodo_tabla_enrutamiento.csv`.
