# Laboratorio 3 - Protocolos de Enrutamiento

Universidad del Valle de Guatemala  
CC3084 - Redes - Semestre II 2026

## Integrantes
- Javier España #23361
- Roberto Barreda #23354

## Objetivo del proyecto
Este repositorio implementa la primera mitad del laboratorio de enrutamiento siguiendo el protocolo definido en los documentos de la carpeta docs. La solución incluye:
- un modelo de router con LSA y cálculo de rutas con Dijkstra,
- generación de una tabla de enrutamiento en CSV,
- soporte básico de detección y corrección de errores con Hamming (7,4),
- una demo ejecutable para validar el flujo inicial del protocolo.

## Estructura del proyecto
- src/common/: utilidades compartidas, como la codificación Hamming.
- src/routers/: lógica del router y cálculo de rutas.
- src/main.py: demo de ejecución local del laboratorio.
- tests/: pruebas básicas para validar Dijkstra y Hamming.
- ROBERTO.md: guía para la segunda mitad del laboratorio.

## Requisitos
- Python 3.10 o superior.

## Ejecución
1. Desde la raíz del proyecto, ejecutar:
   python3 src/main.py
2. Para validar las pruebas básicas:
   pytest -q

## Notas importantes
- El protocolo utilizado sigue el esquema JSON descrito en los documentos, incluyendo los paquetes LSA y los mensajes de datos con el formato {nodo_origen, nodo_destino, mensaje}.
- La implementación actual cubre la parte de construcción de tablas de enrutamiento, serialización de bits y demostración del flujo inicial. La segunda mitad queda documentada en ROBERTO.md para continuar con sockets, HELLO y pruebas reales entre routers.
