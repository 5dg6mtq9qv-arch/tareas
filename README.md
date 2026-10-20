# Tareas

Gestor multiusuario con listas, tareas, subtareas, panel general, vista Kanban, fechas de inicio y límite, prioridades y avisos por correo o Telegram.

## Puesta en marcha

El proyecto usa el entorno virtual `~/.virtualenvs/tareas` y PostgreSQL. En esta máquina ya están instaladas las dependencias, existe la base `tareas` y se aplicaron las migraciones.

```bash
cd ~/Dev/tareas
workon tareas
python manage.py createsuperuser
python manage.py runserver
```

El panel estará en `http://127.0.0.1:8000/`. El enlace **Administración** abre el centro de control de la aplicación para crear usuarios y configurar correo y Telegram. Django Admin sigue disponible en `http://127.0.0.1:8000/admin/` para gestión avanzada. Al entrar por primera vez, cada usuario recibe su propia lista con las columnas Pendiente, En progreso y Completado. Arrastra cada tarjeta a otro estado con ratón o con el dedo; en pantallas pequeñas aparecen los destinos al iniciar el gesto. Las subtareas se mueven de forma independiente en el Kanban y su avance se refleja en el panel general. Al terminar todas, se completa la tarea principal. El selector de estado queda disponible para teclado y accesibilidad.

La interfaz incluye el CSS local de [Tabler 1.4.0](https://github.com/tabler/tabler), distribuido bajo licencia MIT en `static/vendor/tabler/LICENSE`.

La conexión se lee de `.env`. El archivo `.env.example` documenta todas las variables y `.env` está excluido de Git.

Al crear una tarea, la fecha de inicio se propone con la fecha y hora locales actuales; la fecha límite queda vacía hasta que se indique. El formulario usa un calendario en español con horario de 24 horas. Para este control se incluyen archivos locales de [Flatpickr 4.6.13](https://flatpickr.js.org/) y su licencia MIT en `static/vendor/flatpickr/LICENSE.md`.

## Notificaciones

En **Administración** se configuran SMTP, el token del bot de Telegram y las preferencias de cada usuario. Cada usuario también puede cambiar sus canales, chat ID y anticipación desde **Notificaciones**. Para procesar los recordatorios:

```bash
python manage.py send_due_alerts
```

En esta máquina se programó el comando cada cinco minutos con cron, conservando las tareas programadas que ya existían. Para otra instalación:

```cron
*/5 * * * * cd /home/cristian/Dev/tareas && /home/cristian/.virtualenvs/tareas/bin/python manage.py send_due_alerts >> /home/cristian/Dev/tareas/alerts.log 2>&1
```

Para Telegram, cada usuario debe iniciar una conversación con el bot y guardar su `chat_id`. Los avisos enviados se registran para impedir duplicados.

## Verificación

```bash
python manage.py check
python manage.py test
```
