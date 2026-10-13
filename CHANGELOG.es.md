# Registro de cambios

Todos los cambios relevantes de SimpleLog se documentan en este archivo.

## [Sin publicar]

### Añadido
- Registro de cambios, disponible en 5 idiomas y en la aplicación (Ayuda → Novedades).
- Cuando hay una nueva versión disponible, el diálogo de actualización muestra los cambios desde tu versión.

### Cambiado
- SSH: la huella de la clave del servidor se muestra ahora para confirmarla la primera vez que te conectas a un host, y una clave modificada se rechaza.
- Las credenciales y los perfiles guardados ahora solo son legibles por tu cuenta de usuario.

### Corregido
- macOS: la actualización integrada podía borrar toda la carpeta Aplicaciones en lugar de reemplazar solo SimpleLog. Ahora solo reemplaza la app SimpleLog y conserva la anterior si algo falla. Como la actualización se ejecuta desde la versión ya instalada, la 1.0.8 y las anteriores ya no pueden actualizarse solas en macOS: descarga la nueva versión una vez desde la web o con Homebrew.
- Kubernetes: los logs aparecen de inmediato en lugar de solo después de 200 líneas.
- Loki, GCP, Datadog y Fly.io: las mismas líneas de log ya no reaparecen una y otra vez al seguir una fuente.
- Loki, Datadog y Elasticsearch: la carga inicial ahora muestra los logs más recientes en lugar de los más antiguos del periodo. GCP ya no omite entradas en los picos de actividad.
- Un fallo de red breve ya no detiene el seguimiento de una fuente con una ventana de error: SimpleLog reintenta y solo informa de un error tras varios fallos seguidos.
- Pulsar Intro en un campo de texto (búsqueda, filtro, formularios) ya no inserta una línea separadora en el log actual.
- Abrir un log en un panel dividido cuando la pestaña ya tiene 9 paneles ahora muestra un mensaje, en lugar de iniciar en silencio un log que nunca se muestra.
- Abrir muchas conexiones guardadas ya no ralentiza la aplicación con el tiempo: sus diálogos, temporizadores y conexiones SSH se liberan al cerrarlos.
- Archivos locales: el seguimiento de un archivo sigue funcionando tras su rotación o vaciado, las líneas escritas en dos partes ya no se dividen y los caracteres acentuados ya no se corrompen.

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
