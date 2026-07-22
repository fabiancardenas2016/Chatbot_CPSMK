# Despliegue en Oracle Cloud Infrastructure (OCI) — nivel gratuito (Always Free)

Esta guía despliega el proyecto completo (backend + frontend, un solo
servicio) en una instancia **Always Free** de OCI usando Docker.

## 1. Crear la instancia

1. Ingresa a la consola de OCI → **Compute → Instances → Create Instance**.
2. Elige una forma (*shape*) del nivel gratuito, por ejemplo:
   - `VM.Standard.A1.Flex` (Ampere, hasta 4 OCPU / 24 GB en el nivel gratuito), o
   - `VM.Standard.E2.1.Micro` (x86, nivel gratuito clásico).
3. Imagen: **Ubuntu 22.04** (o superior).
4. En "Networking", asegúrate de asignar una IP pública.
5. Descarga la llave SSH privada generada (o usa la tuya).

## 2. Configurar el firewall / Security List

En la VCN de la instancia, agrega una regla de entrada (*Ingress Rule*):
- Origen: `0.0.0.0/0`
- Protocolo: TCP
- Puerto destino: `80` (y `443` si vas a configurar HTTPS)

Dentro de la instancia (Ubuntu usa `iptables`/`netfilter` u `ufw`), habilita también el puerto:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

## 3. Conectarse por SSH e instalar Docker

```bash
ssh -i tu_llave.pem ubuntu@IP_PUBLICA_DE_LA_INSTANCIA

# Instalar Docker y Docker Compose
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Permite ejecutar docker sin sudo (opcional, requiere reiniciar sesión)
sudo usermod -aG docker $USER
```

## 4. Subir el proyecto a la instancia

Desde tu máquina local (fuera de la instancia):

```bash
scp -i tu_llave.pem -r rrhh-chatbot ubuntu@IP_PUBLICA_DE_LA_INSTANCIA:~/
```

O bien, clona el repositorio directamente dentro de la instancia si lo subiste a un
repositorio Git.

## 5. Configurar variables de entorno

```bash
cd ~/rrhh-chatbot
cp .env.example .env
nano .env    # coloca tu GOOGLE_API_KEY gratuita
```

Asegúrate de haber copiado también los 4 PDF de RR.HH. en
`backend/data/documentos/` (ver `backend/data/documentos/LEEME.txt`).

## 6. Construir y levantar el servicio

```bash
docker compose build
docker compose up -d
```

Verifica que esté activo:

```bash
curl http://localhost/api/salud
# {"estado":"ok"}
```

Desde tu navegador, visita: `http://IP_PUBLICA_DE_LA_INSTANCIA/`

## 7. (Opcional) HTTPS con dominio propio

Si cuentas con un dominio apuntando a la IP de la instancia, puedes usar
[Caddy](https://caddyserver.com/) o `certbot` + Nginx como proxy inverso
delante del contenedor (puerto 8000) para obtener HTTPS automático con
Let's Encrypt, sin costo adicional.

## 8. Actualizar el despliegue

```bash
cd ~/rrhh-chatbot
git pull            # si usas Git
docker compose build
docker compose up -d
```

## 9. Alternativa sin Docker (systemd + uvicorn)

Si prefieres no usar contenedores:

```bash
sudo apt-get install -y python3.11 python3.11-venv
cd ~/rrhh-chatbot/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # y edítalo con tu API key

# Prueba manual
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 2
```

Para dejarlo corriendo permanentemente, crea un servicio systemd
(`/etc/systemd/system/rrhh-chatbot.service`) que ejecute el comando
`uvicorn` anterior con `WorkingDirectory=/home/ubuntu/rrhh-chatbot/backend`
y `Restart=always`, y colócalo detrás de Nginx en el puerto 80.
