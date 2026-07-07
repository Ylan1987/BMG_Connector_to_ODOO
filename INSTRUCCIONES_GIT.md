# Cómo configurar Git en tu Servidor (Docker)

Dado que **tu servidor no tiene una IP fija** y trabajas mediante contenedores **Docker**, la **Opción 1** es definitivamente la mejor alternativa. Al usar la Opción 1, es el contenedor el que se conecta a GitHub (y GitHub sí tiene una dirección fija). 

---

## Opción 1: Hacer `git pull` manual (Recomendada para IP Dinámica)

En este método, trabajas en tu PC, subes los cambios a GitHub, y luego desde el contenedor del servidor descargas la actualización.

**Paso a paso en el servidor (Configuración inicial por única vez):**
1. Entra a la consola de tu contenedor Docker (por ejemplo, `docker exec -it bmg_sincronizador bash`).
2. Ve a la carpeta de la aplicación:
   ```bash
   cd /app
   ```
3. (Opcional) Si en tu consola no existe el comando git, puedes instalarlo temporalmente así:
   ```bash
   apt-get update && apt-get install -y git
   ```
   *(Nota: Ya dejamos agregado git en tu docker-compose.yml, por lo que a partir de ahora al reiniciar o reconstruir el contenedor, git se instalará automáticamente).*
4. Si la carpeta aún no está vinculada a Git, inicialízala y conéctala a tu GitHub:
   ```bash
   git config --global --add safe.directory /app
   git init
   git remote add origin https://github.com/Ylan1987/BMG_Connector_to_ODOO.git
   ```
   *(El comando `safe.directory` sirve para evitar el error de "dubious ownership" que tira Git porque los dueños de los archivos físicos en el NAS son diferentes al root de Docker).*
5. Sincroniza por primera vez y dile a Git qué rama debe seguir:
   ```bash
   git fetch
   git reset --hard origin/test
   git checkout test
   # (Nota: si usas otra rama, cambia 'test' por 'main' o 'master').
   ```

**¿Cómo actualizar tu servidor de ahora en adelante?**
Cada vez que hagas un `git push` desde tu PC, simplemente entras al servidor (al contenedor), vas a `/app` y ejecutas:
```bash
git pull origin test
```
*(De nuevo, cambia `test` por la rama que estés usando, como `main` o `master`).*

---

## ¿Y qué pasa con la Opción 2 (Git Push directo)?

Como la IP de tu servidor cambia, la configuración de tu PC para apuntar al servidor (`git remote add produccion ssh://...`) dejaría de funcionar cada vez que cambie la IP, obligándote a actualizar la IP a mano constantemente.

Si **realmente** quisieras usar la Opción 2, tendrías que usar una de estas soluciones externas:
1. **Un servicio de DNS Dinámico (DDNS):** Como *DuckDNS* o *No-IP*.
2. **Una VPN como Tailscale o ZeroTier:** Para asignar una IP local estática.

*Recomendación: Quédate con la **Opción 1**.*



