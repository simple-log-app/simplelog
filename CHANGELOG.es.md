# Registro de cambios

Todos los cambios relevantes de SimpleLog se documentan en este archivo.

## [Sin publicar]

### Corregido
- La ventana de descarga de la actualización ya no muestra la barra de título del sistema.

## [2.2.3] - 2026-10-15

### Cambiado
- Las conexiones WebSocket de Cloudflare ahora requieren TLS 1.2 o superior.

## [2.2.2] - 2026-10-15

### Corregido
- Los botones Cerrar/Aceptar/Cancelar/Sí/No de los diálogos ahora siguen el idioma de la aplicación.

## [2.2.1] - 2026-10-15

### Corregido
- Los cuadros de mensaje (Acerca de, actualización, errores, confirmaciones) también pierden la barra de título del sistema, como los demás diálogos.

## [2.2.0] - 2026-10-15

### Cambiado
- Los cuadros de diálogo ya no tienen la barra de título del sistema: sin botones de minimizar / maximizar y no se pueden mover; ciérralos con ✕ o Esc.

## [2.1.3] - 2026-10-15

### Corregido
- Linux: «Añadir» y las conexiones guardadas vuelven a funcionar en la aplicación instalada (no hacían nada en la 2.1.2).
- El menú Auto / Día / Noche ya no se ve oscuro en modo Día.

## [2.1.2] - 2026-10-15

### Cambiado
- Reorganización interna de la aplicación; no cambia nada en el aspecto ni el funcionamiento de SimpleLog.

## [2.1.1] - 2026-10-15

### Corregido
- El cursor de ratón de «carga» ya no se queda varios segundos al pulsar «Añadir» o abrir una conexión guardada (Linux/GNOME).

## [2.1.0] - 2026-10-14

### Añadido
- El tema ahora puede seguir el ajuste claro / oscuro de tu sistema: elige «Auto» con la flecha junto al botón Día / Noche.
- Filtro por nivel: muestra u oculta las líneas ERROR, WARN, INFO, DEBUG y TRACE con las fichas de la pestaña Filtro.
- Búsqueda y filtro: nuevas opciones «distinguir mayúsculas» y «expresión regular», y se sugieren tus términos recientes al escribir (↓ en un campo vacío para listarlos).
- Reglas de resaltado (menú Edición): colorea en todos los logs las palabras que te importan, con distinción de mayúsculas y expresiones regulares opcionales.
- Marcadores: marca líneas con Ctrl+B (o el menú contextual) y salta entre ellas con F2 / Mayús+F2, o quítalos todos a la vez (Ctrl+Mayús+B).
- Exportar: guarda en un archivo las líneas mostradas (tras tus filtros) o solo la selección, desde el menú Archivo (Ctrl+Mayús+E) o el menú contextual.
- Vista combinada (menú Edición o menú contextual): muestra varios logs abiertos en una sola pestaña, en orden cronológico, con cada línea indicando su origen.
- Las pestañas remotas muestran su estado de conexión (punto de color en el logotipo) y se reconectan solas cuando el flujo se corta, sin duplicar líneas; se puede desactivar en el menú Archivo.
- Nuevas fuentes de logs: el diario local de systemd, Heroku, Render, Splunk, Better Stack y Sentry (eventos de error).

### Cambiado
- Añadir conexión: las opciones «Split» de «Abrir como» aparecen atenuadas mientras no haya ningún log abierto, ya que aún no hay nada que dividir.

### Corregido
- El cursor de «carga» del ratón ya no permanece unos 12 segundos al iniciar SimpleLog (Linux/GNOME).

## [2.0.0] - 2026-10-14

### Añadido
- Búsqueda: F3 pasa al siguiente resultado y Mayús+F3 al anterior; los atajos aparecen en la información sobre herramientas de los botones.
- Modo Día / Noche: cambia el tema con el botón situado a la derecha de la barra de menús (o con Ctrl+Mayús+L); tu elección se recuerda.

### Cambiado
- Nuevo aspecto: paleta oscura renovada con un acento lima, para una mejor legibilidad.
- Fuentes remotas: la lista solo muestra los servicios con conexiones guardadas, con un enlace «+ Nueva conexión» y eliminación en dos pasos.
- Añadir una conexión: un selector filtrable en 4 columnas con el logotipo oficial de cada servicio y un formulario de conexión más claro.
- Los logotipos de los servicios aparecen en las pestañas y la opción «Abrir como» ocupa una sola fila.

### Corregido
- El botón Y / O entre los términos de búsqueda y de filtro ahora se muestra en tu idioma.

## [1.0.9] - 2026-10-13

### Añadido
- Registro de cambios, disponible en 5 idiomas y en la aplicación (Ayuda → Novedades).
- Cuando hay una nueva versión disponible, el diálogo de actualización muestra los cambios desde tu versión.
- Nueva opción «Ajustar» en la barra del log: desactívala para mostrar cada log en una sola línea (desplazamiento lateral para las largas), lo que es más rápido con logs muy grandes.

### Cambiado
- SSH: la huella de la clave del servidor se muestra ahora para confirmarla la primera vez que te conectas a un host, y una clave modificada se rechaza.
- Las credenciales y los perfiles guardados ahora solo son legibles por tu cuenta de usuario.
- Mucho más rápido con flujos de logs intensos (SSH, Docker, Kubernetes, stdin, archivos): las líneas se añaden en grupos, y los logs largos siguen siendo fluidos al seguirlos, redimensionar o cambiar de pestaña.
- Ctrl+W ahora cierra la pestaña actual; cerrar todos los logs es Ctrl+Mayús+W.
- Las marcas de tiempo de la vista de logs ahora se muestran en tu hora local en lugar de UTC.
- Arranque más rápido, y abrir un archivo grande con un número muy alto de líneas ahora es casi instantáneo.
- Las tarjetas de proveedores de «Añadir conexión» ahora muestran una breve descripción de cada fuente al pasar el ratón.
- Los mensajes de estado, errores de conexión y descripciones emergentes que siempre estaban en inglés ahora siguen el idioma elegido.
- Las actualizaciones ahora se comprueban con la suma de verificación publicada con la versión, y una descarga dañada se descarta.

### Corregido
- CloudWatch: una conexión basada en un perfil de AWS ahora usa la región definida para ese perfil en `~/.aws/config`.
- La aplicación ya no se cierra cuando una conexión falla justo después de cerrar su pestaña, ni cuando su archivo de configuración de AWS tiene un perfil duplicado.
- Archivo → Abrir (Ctrl+O) ya no abre el archivo dos veces.
- Los logs de Docker, Kubernetes, SSH y los recibidos por pipe ya no se detienen en silencio ante una línea con caracteres no válidos.
- Cargar un lote muy grande de líneas (por ejemplo `cat grande.log | simplelog`) ya no deja filas fantasma en la vista.
- Fly.io: un token no válido o una aplicación desconocida ahora muestran un error en lugar de un log vacío interminable.
- Azure: las condiciones adicionales de su consulta (por ejemplo, sobre la gravedad) se conservan durante el seguimiento, y las filas ingeridas con retraso ya no se pierden.
- Kubernetes: un pod que imprime muchas advertencias ya no bloquea el flujo de logs.
- La actualización automática en Linux (AppImage) ahora funciona cuando la ruta de instalación contiene una comilla.
- Se rechazan las actualizaciones cuando las sumas de verificación publicadas no incluyen el archivo descargado.
- El título «Error» y los botones «Ant./Sig.» y «+ clave=val» ahora siguen el idioma elegido.
- Los filtros clave=valor son unas 2× más rápidos con logs JSON.
- macOS: la actualización integrada podía borrar toda la carpeta Aplicaciones en lugar de reemplazar solo SimpleLog. Ahora solo reemplaza la app SimpleLog y conserva la anterior si algo falla. Como la actualización se ejecuta desde la versión ya instalada, la 1.0.8 y las anteriores ya no pueden actualizarse solas en macOS: descarga la nueva versión una vez desde la web o con Homebrew.
- Kubernetes: los logs aparecen de inmediato en lugar de solo después de 200 líneas.
- Loki, GCP, Datadog y Fly.io: las mismas líneas de log ya no reaparecen una y otra vez al seguir una fuente.
- Loki, Datadog y Elasticsearch: la carga inicial ahora muestra los logs más recientes en lugar de los más antiguos del periodo. GCP ya no omite entradas en los picos de actividad.
- Un fallo de red breve ya no detiene el seguimiento de una fuente con una ventana de error: SimpleLog reintenta y solo informa de un error tras varios fallos seguidos.
- Pulsar Intro en un campo de texto (búsqueda, filtro, formularios) ya no inserta una línea separadora en el log actual.
- Abrir un log en un panel dividido cuando la pestaña ya tiene 9 paneles ahora muestra un mensaje, en lugar de iniciar en silencio un log que nunca se muestra.
- Abrir muchas conexiones guardadas ya no ralentiza la aplicación con el tiempo: sus diálogos, temporizadores y conexiones SSH se liberan al cerrarlos.
- Archivos locales: el seguimiento de un archivo sigue funcionando tras su rotación o vaciado, las líneas escritas en dos partes ya no se dividen y los caracteres acentuados ya no se corrompen.
- Búsqueda: las coincidencias se resaltan en amarillo translúcido, en el lugar correcto en las líneas con salto de línea; se respeta el AND / OR entre términos; las filas JSON con coincidencia se resaltan; y la vista ya no vuelve al primer resultado mientras se sigue un log.
- Hacer clic derecho o seleccionar con el ratón en una línea JSON ya no la expande ni la contrae; solo lo hace un clic simple.
- Abrir un archivo con `simplelog archivo.log` desde otra carpeta mientras SimpleLog está en ejecución ahora funciona.
- Cerrar una pestaña o salir ya no congela la aplicación durante varios segundos.
- Activar o desactivar las marcas de tiempo ahora redimensiona correctamente las líneas con salto de línea.
- Las conexiones y credenciales guardadas ya no pueden perderse si la aplicación falla al guardar.
- Elasticsearch 8 y posteriores: el seguimiento de logs vuelve a funcionar (usaba una ordenación que las versiones recientes rechazan).
- Actualizaciones: se detecta una descarga incompleta, y instalar una actualización .deb ya no congela la ventana.
- CloudWatch, Docker y SSH: listar grupos de logs, streams y contenedores, y abrir un log SSH, ya no congela la aplicación mientras espera a la red.
- El explorador de archivos SFTP, las sesiones SSH / GCP / Azure restauradas y la lista de clústeres de Kubernetes ya no congelan la aplicación mientras esperan a la red.
- La insignia de origen en la barra del log mostraba una etiqueta interna como «src_ssh»; ahora muestra el nombre del origen.
- Las conexiones guardadas de Google Cloud ahora muestran su proyecto junto al nombre.
- Azure: el seguimiento en vivo ahora también funciona con consultas escritas en una sola línea o con un límite de filas (`take`/`limit`) antes del filtro.
- CloudWatch: los eventos que llegan con unos segundos de retraso ya no se pierden al seguir un grupo.
- Railway: seguir un servicio ya no guarda todas las líneas en memoria, y elegir varios servicios seguidos ya no abre conexiones de más.
- Azure: la carga inicial de una tabla o de una consulta que limita sus filas ahora muestra las filas más recientes en lugar de las más antiguas.
- Railway: seguir un servicio solo obtiene las líneas nuevas en lugar de volver a descargar todos sus logs en cada actualización.

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
