# Registro de cambios

Todos los cambios relevantes de SimpleLog se documentan en este archivo.

## [Sin publicar]

### Añadido
- Registro de cambios, disponible en 5 idiomas y en la aplicación (Ayuda → Novedades).
- Cuando hay una nueva versión disponible, el diálogo de actualización muestra los cambios desde tu versión.

## [1.0.8] - 2026-09-30

### Añadido
- Al reabrir una conexión guardada, se reconecta automáticamente y se restauran el destino seleccionado (grupo de logs, proyecto, servicio, pod, worker…) y las opciones, para todos los proveedores. Solo hay que pulsar Abrir.

### Corregido
- AWS CloudWatch: las credenciales guardadas ahora se rellenan al reabrir una conexión.

## [1.0.7] - 2026-08-19

### Corregido
- macOS: las compilaciones de la release vuelven a funcionar (fallaban desde la 1.0.4).
- Los enlaces y la comprobación de actualizaciones apuntan a la nueva organización de GitHub simple-log-app.

## [1.0.6] - 2026-07-29

### Corregido
- La rueda del ratón ya no cambia por error los valores de las listas desplegables al desplazarse.

## [1.0.5] - 2026-07-29

### Añadido
- Menú contextual (clic derecho) para copiar las líneas de log seleccionadas.

## [1.0.4] - 2026-07-29

### Corregido
- Ahora se pueden seleccionar varias líneas de log a la vez en el visor.

## [1.0.3] - 2026-05-25

### Corregido
- macOS: corregido un cierre inesperado al iniciar.

## [1.0.2] - 2026-05-25

### Corregido
- macOS: corregido un cierre inesperado al iniciar.

## [1.0.1] - 2026-05-21

### Cambiado
- Limpieza interna y mejor cobertura de pruebas.

## [1.0.0] - 2026-05-20

### Añadido
- Primera versión: visor de logs para archivos locales, stdin, AWS CloudWatch, SSH, Docker, Kubernetes, Vercel, Google Cloud, Azure, Loki, Datadog, Elasticsearch, Railway, Fly.io y Cloudflare Workers.
