# Operación del servidor

Tareas de mantenimiento que requieren root en las VMs. Los comandos se pegan
en la VM indicada; ninguno borra datos.

## Migraciones de la base (VM-BD)

`db/schema.sql` crea una base **nueva** (borra el esquema). Una base que ya
tiene datos se actualiza con los archivos de `db/migraciones/`, en orden y una
sola vez cada uno. Cada migración es una transacción: si falla, no cambia nada.

```bash
sudo -u postgres psql -d lente -v ON_ERROR_STOP=1 -f 001_trabajos_atascados_y_abandono.sql
```

Después de aplicar una migración que cambia el worker, reiniciarlo en la VM-APP:
`sudo systemctl restart "lente-worker@*"`.

| Migración | Qué hace |
|---|---|
| `001_trabajos_atascados_y_abandono` | Reintenta los trabajos de IA que quedaron «procesando» si un worker se detuvo (3 min; 20 min al preparar textos) y marca como abandonadas las actividades sin respuestas durante `horas_para_abandono` (3 h), con análisis de ánimo (RF-21) |

## Copias de seguridad (VM-BD, RNF-04)

`deploy/respaldo/` contiene el script y un temporizador de systemd que guarda
una copia diaria (2:00 UTC, que son las 9:00 p. m. en Colombia) en `/var/backups/lente`, verifica que se pueda
leer y conserva 14 días.

```bash
sudo install -d -o postgres -g postgres -m 700 /var/backups/lente
sudo install -m 755 lente-respaldo.sh /usr/local/bin/lente-respaldo.sh
sudo cp lente-respaldo.service lente-respaldo.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lente-respaldo.timer
sudo systemctl start lente-respaldo.service      # primera copia ahora
journalctl -u lente-respaldo.service -n 5        # resultado
```

Restaurar en una base de prueba, sin tocar la real:

```bash
sudo -u postgres createdb lente_restaurada
sudo -u postgres pg_restore -d lente_restaurada /var/backups/lente/lente-AAAAMMDD-HHMM.dump
```

Las copias quedan en la misma VM: protegen contra errores y borrados, no contra
la pérdida del disco. Para eso, copiarlas periódicamente a otro servidor
(pendiente de acordar con TI).

## Firewall de la VM-IA (RNF-05)

Ollama solo debe aceptar solicitudes de la VM-APP. SSH queda abierto para
administrar la máquina.

```bash
sudo ufw allow 22/tcp
sudo ufw allow from 10.60.14.182 to any port 11434 proto tcp
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
sudo ufw status verbose
```

Para deshacerlo: `sudo ufw disable`.

## Pendiente con TI

- HTTPS para la API (certificado y un proxy como Nginx delante de `:8000`).
- Que solo la VM-APP quede expuesta a internet, como pide el levantamiento v1.1.
