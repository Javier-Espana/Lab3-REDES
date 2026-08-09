# Tareas pendientes para Roberto

## Estado actual
La primera mitad del laboratorio ya quedó implementada en este repositorio:
- simulación de un router con LSA y cálculo de rutas con Dijkstra,
- generación de la tabla de enrutamiento en CSV,
- soporte básico de Hamming (7,4) para la capa de detección/corrección,
- ejemplo ejecutable desde la carpeta src.

## Lo que debe completar en la segunda mitad
1. Convertir la simulación en una arquitectura de procesos o hilos reales.
   - Cada nodo/router debe correr de forma independiente.
   - Debe haber un proceso de routing y otro de forwarding en paralelo.
2. Implementar el intercambio real de LSA entre routers.
   - Los routers deben descubrir vecinos vía HELLO y reenviar los LSA.
   - Debe manejarse el control de secuencias por origen para evitar ciclos.
3. Integrar el plano de datos con sockets.
   - El cliente y el servidor deben comunicarse con su router más cercano.
   - Los routers intermedios deben reenviar el paquete completo usando la tabla de enrutamiento.
4. Ajustar el formato a los nombres de la topología real de las tres parejas.
   - El protocolo debe mantenerse compatible con el esquema JSON definido en el protocolo.
5. Probar la interoperabilidad con las otras dos parejas en la red privada (Tailscale).

## Qué revisar antes de entregar
- Ejecutar python3 src/main.py desde la raíz del proyecto.
- Confirmar que se generan los archivos CSV de tabla de enrutamiento.
- Validar que el mensaje de aplicación se serializa y se deserializa correctamente.

## Sugerencia de siguiente paso
Completar la implementación con sockets TCP/UDP, HELLO periódico y un flujo de intercambio de LSA entre nodos reales. Esto dejará el laboratorio listo para la segunda fase de pruebas en clase.
