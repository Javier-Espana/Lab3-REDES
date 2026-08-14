# Laboratorio 3 - Protocolos de Enrutamiento y Malla Distribuida

Universidad del Valle de Guatemala  
CC3084 - Redes - Semestre II 2026

## Integrantes
- Javier Espana #23361
- Roberto Barreda #23354

---

## Objetivo del Proyecto

Este repositorio implementa un sistema de enrutamiento distribuido con el protocolo **Link-State (LSA)** y cálculo de rutas mediante el algoritmo de **Dijkstra**. Incluye:

- **Plano de Control**: Intercambio periódico de paquetes `HELLO` (descubrimiento de vecinos) y `LSA` (inundación de estado del enlace).
- **Plano de Datos**: Reenvío salto a salto de paquetes de datos end-to-end (ATM -> Router(es) -> Banco).
- **Control de Errores por Capas**:
  - Plano de control (`HELLO` y `LSA`): Transmisión bajo el algoritmo `none` (bits ASCII directos sin redundancia).
  - Plano de datos (`ATM` / `BANK`): Codificación por bloques **Hamming (7,4)** con un encabezado de 16 bits (`num_blocks`) para detección y corrección de errores de 1 bit.
- **Formato del Socket (Protocolo Compartido Inter-Grupo)**:
  Trama de red terminada en salto de línea: `<algoritmo>|<cadena_de_bits>\n`
- **Tablas de Enrutamiento (CSV)**: Exportación automática en el estándar acordado `destino,siguiente_salto,costo,ip,puerto`.
- **Menú Interactivo del Cajero ATM**: Consola limpia e interactiva con comandos para transacciones bancarias, control de logs de fondo (`logs on/off`) y salida limpia (`exit`).
- **Conectividad Distribuida vía Tailscale**: Ejecución en máquinas independientes conectadas por red privada VPN.
- **Interoperabilidad Total**: Compatibilidad garantizada para conectarse e intercambiar paquetes con el proyecto de los compañeros (`Lab3-Redes`).

---

## Estructura del Proyecto

```
Lab3-REDES/
├── topology.json            <- FUENTE UNICA DE VERDAD (IPs, nodos, enlaces y end_hosts)
├── src/
│   ├── main.py              <- Punto de entrada principal (CLI de ejecución)
│   ├── network_settings.py  <- Control de modo USE_TAILSCALE = True/False
│   ├── common/
│   │   ├── config.py        <- Parseador de topología insensible a mayúsculas/minúsculas
│   │   ├── framing.py       <- Capa de enmarcado <algoritmo>|<bits>\n
│   │   └── hamming.py       <- Hamming (7,4) por bloques con encabezado de 16 bits
│   ├── routers/
│   │   └── router.py        <- Router Link-State (HELLO, LSA, Dijkstra y Forwarding)
│   └── apps/
│       ├── atm_client.py    <- Cliente ATM (Cajero interactivo)
│       └── bank_server.py   <- Servidor Bancario (Manejo de cuentas y sesiones)
├── tests/
│   └── test_routing.py      <- Pruebas unitarias e interoperabilidad inter-grupo
└── output/                  <- Tablas de enrutamiento CSV generadas automáticamente
```

---

## Requisitos

- Python **3.10** o superior.
- **Tailscale** instalado y activo en cada máquina (para modo distribuido).

---

## Configuración: `topology.json`

Toda la red se define en el archivo de configuración **`topology.json`**:

- **`machines`**: Dirección IP de Tailscale de cada participante (`Espana`, `Angel`, `Tono`, etc.).
- **`nodes`**: Routers de la red, cada uno con su propietario (`owner`) y puerto.
- **`links`**: Enlaces bidireccionales entre routers con su costo.
- **`end_hosts`**: Nodos terminales (`ATM1`, `BANK1`) con su propietario, puerto y gateway.

### Ejemplo de `topology.json`:

```json
{
  "machines": {
    "Espana": "100.119.213.97",
    "Angel": "100.71.208.101"
  },
  "nodes": {
    "R1": { "owner": "Espana", "port": 5001 },
    "R2": { "owner": "Espana", "port": 5002 },
    "R3": { "owner": "Espana", "port": 5003 },
    "R4": { "owner": "Angel", "port": 5004 },
    "R5": { "owner": "Angel", "port": 5005 },
    "R6": { "owner": "Angel", "port": 5006 }
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
    "ATM1": { "owner": "Espana", "port": 6101, "gateway": "R1", "cost": 1 },
    "BANK1": { "owner": "Angel", "port": 6102, "gateway": "R4", "cost": 1 }
  }
}
```

---

## Ejecución del Proyecto

### Formas de Ejecución (`src/main.py`)

Puedes pasar el nombre del propietario o del nodo como **argumento directo** (posicional) o mediante flags:

#### 1. Ejecutar todos los nodos de un participante (Recomendado)
```bash
# Ejecutar nodos de Espana (R1, R2, R3, ATM1)
python src/main.py Espana

# O con flag explícito:
python src/main.py -p Espana
```

#### 2. Ejecutar un nodo individual
```bash
python src/main.py R1
python src/main.py BANK1
python src/main.py ATM1
```

#### 3. Ejecución Local (Pruebas en una sola máquina)
Agrega el flag `--local` para forzar el uso de `127.0.0.1`:
```bash
python src/main.py Espana --local
```
O cambia en `src/network_settings.py`: `USE_TAILSCALE = False`.

#### 4. Demostración Automática Completa (Simulación Local)
```bash
python src/main.py --demo
```

---

## Menú Interactivo del Cajero ATM

Cuando ejecutas un conjunto de nodos que incluye un Cajero ATM (por ejemplo `python src/main.py Espana`), se abre automáticamente la consola interactiva del ATM.

### Características y Silenciamiento de Logs
Para evitar que los mensajes periódicos del router (`HELLO`, `LSA`, actualización de rutas) interrumpan lo que estás escribiendo en el cajero, **los logs del router están silenciados por defecto mientras usas el ATM**.

```
==================================================
               MENU CAJERO ATM (ATM1)        
==================================================
Comandos disponibles:
  - login               : Iniciar sesion (pide tarjeta y PIN)
  - withdraw [monto]    : Realizar retiro de dinero
  - logout              : Cerrar sesion
  - logs [on|off]       : Mostrar/ocultar logs de red en tiempo real
  - exit                : Salir del programa
```

### Comandos del Menú ATM:
- **`login`**: Solicita tarjeta y PIN. Autentica contra el banco remoto.
  - Tarjetas de prueba disponibles: `4111111111111111` (PIN `1234`), `5500005555555559` (PIN `0000`), `23221` (PIN `2310`).
- **`withdraw [monto]`**: Solicita el monto a retirar (ej. `withdraw 100`).
- **`logout`**: Cierra la sesión activa en el banco.
- **`logs` / `logs on` / `logs off`**: Permite activar o desactivar los logs del enrutador en tiempo real sin detener el programa.
- **`exit` / `quit`**: Cierra el cajero y detiene de forma limpia todos los nodos que se estaban ejecutando en esa consola.

---

## Ejecución Distribuida con Tailscale

### Paso 1. Iniciar Tailscale
Asegúrate de que todos los integrantes estén conectados a la misma red de Tailscale:
```bash
tailscale ip -4
```

### Paso 2. Configurar `topology.json`
Edita la sección `machines` en `topology.json` colocando las IPs de Tailscale reales de cada integrante (`Espana`, `Angel`, etc.).

Asegúrate de que `src/network_settings.py` contenga:
```python
USE_TAILSCALE = True
```

### Paso 3. Iniciar Nodos por Participante
Cada integrante ejecuta su comando en su consola:

- **España (Máquina 1)**:
  ```bash
  python src/main.py Espana
  ```
- **Angel (Máquina 2)**:
  ```bash
  python src/main.py Angel
  ```

---

## Interoperabilidad con el Proyecto de Compañeros (`Lab3-Redes`)

Nuestro proyecto en `src/` puede conectarse e intercambiar paquetes directamente con los nodos del repositorio clonado `Lab3-Redes/`.

Si un participante ejecuta su parte con el código de `Lab3-Redes/`:
1. Debe sincronizar `topology.json` y ejecutar `python topology_generator.py` dentro de `Lab3-Redes/` para actualizar las IPs de sus archivos `configs/*.json`.
2. Luego inicia su router/nodo normalmente:
   ```bash
   python router.py configs/R4.json
   python bank/server.py configs/BANK1.json
   ```
3. Tu nodo en `src/` (`python src/main.py Espana`) se conectará automáticamente a sus routers por Tailscale, intercambiará paquetes `HELLO` y `LSA`, y procesará transacciones del cajero.

---

## Pruebas Unitarias e Interoperabilidad

Para ejecutar la suite completa de pruebas unitarias y la prueba de integración directa con `Lab3-Redes`:

```bash
python -m unittest discover tests
```
