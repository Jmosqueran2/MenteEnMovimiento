# Despliegue en AWS (AWS Academy Learner Lab)

Arquitectura final:

```
Navegador ──HTTPS──▶ EC2 (Ubuntu 24.04)
                      ├─ Caddy: HTTPS automático + archivos de React
                      ├─ Django + DRF (gunicorn, puerto 8000)  ──▶ RDS PostgreSQL
                      │                                        ──▶ S3 (fotos y audios de Mi Historia)
                      └─ Microservicio de visión FastAPI (puerto 8001, WebSocket)
```

El HTTPS es obligatorio: sin él, el navegador no deja usar la cámara ni el
micrófono. Se usa un dominio gratuito `sslip.io` con la IP pública
(p. ej. `https://3-85-12-4.sslip.io`) y Caddy obtiene el certificado solo.

Tiempo total: unos 40 minutos (la mayor parte es esperar a RDS y a la instalación).

---

## 0. Antes de empezar

1. Sube a GitHub la última versión del código (`git push`). El servidor la descarga desde ahí.
2. Si el repositorio es **privado**, ten a mano un token de GitHub
   (Settings → Developer settings → Personal access tokens) para clonarlo.
3. En AWS Academy: **Start Lab**, espera a que el punto se ponga verde y pulsa **AWS**.
   Trabaja siempre en la región **N. Virginia (us-east-1)**.

## 1. S3: bucket para Mi Historia

1. Busca **S3** → **Create bucket**.
2. **Bucket name**: un nombre único, en minúsculas, p. ej. `mente-historia-tunombre`.
3. Deja **Block all public access** activado (el bucket es privado; la app usa
   enlaces firmados que caducan en una hora).
4. **Create bucket**. Anota el nombre.

## 2. EC2: el servidor

1. Busca **EC2** → **Launch instance**.
2. **Name**: `mente-servidor`.
3. **AMI**: **Ubuntu Server 24.04 LTS** (64-bit x86).
4. **Instance type**: **t3.medium** (4 GB de RAM; los modelos de visión no caben en menos).
5. **Key pair**: `vockey` (la llave del Learner Lab; se descarga en *AWS Details* → *Download PEM*).
6. **Network settings** → marca:
   - Allow SSH traffic (mejor desde *My IP*)
   - Allow HTTPS traffic from the internet
   - Allow HTTP traffic from the internet (Caddy lo necesita para el certificado)
7. **Configure storage**: **30 GiB** gp3.
8. **Advanced details** → **IAM instance profile**: **LabInstanceProfile**
   (así el servidor puede escribir en S3 sin guardar claves).
9. **Launch instance**.

### IP fija (recomendado)

Sin esto, la IP (y con ella el dominio) cambia cada vez que el laboratorio se apaga.

1. EC2 → **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**.
2. Selecciónala → **Actions** → **Associate Elastic IP address** → elige `mente-servidor` → **Associate**.

## 3. RDS: base de datos PostgreSQL

1. Busca **RDS** → **Create database** → **Standard create**.
2. **Engine**: **PostgreSQL**.
3. **Templates**: **Free tier** (o *Sandbox*).
4. **DB instance identifier**: `mente-db`.
5. **Master username**: `mente`. **Master password**: solo letras y números (p. ej. `Mente2026Segura`).
6. **Instance class**: `db.t3.micro` o `db.t4g.micro`. **Storage**: 20 GiB.
7. **Connectivity** → **Connect to an EC2 compute resource** → elige `mente-servidor`
   (AWS abre el puerto 5432 solo para el servidor; la base no queda en internet).
8. **Additional configuration** → **Initial database name**: `mente`.
   Desactiva *Enhanced monitoring* si aparece (el laboratorio no lo permite).
9. **Create database** y espera unos 10 minutos a que diga *Available*.
10. Entra a `mente-db` y copia el **Endpoint** (algo como `mente-db.xxxx.us-east-1.rds.amazonaws.com`).

## 4. Instalar en el servidor

1. EC2 → selecciona `mente-servidor` → **Connect** → pestaña **EC2 Instance Connect** → **Connect**
   (se abre una terminal en el navegador).
2. Copia y pega (cambia los datos de las líneas marcadas):

```bash
sudo git clone https://github.com/Jmosqueran2/MenteEnMovimiento.git /opt/mente
sudo chown -R ubuntu:ubuntu /opt/mente
cd /opt/mente
cp deploy/aws.env.ejemplo deploy/aws.env
nano deploy/aws.env
```

3. En `nano` completa:

```
AWS_STORAGE_BUCKET_NAME=mente-historia-tunombre          # ← tu bucket
DATABASE_URL=postgres://mente:Mente2026Segura@mente-db.xxxx.us-east-1.rds.amazonaws.com:5432/mente   # ← tu endpoint y clave
```

   Guarda con `Ctrl+O`, `Enter`, y sal con `Ctrl+X`.

4. Instala (10–15 minutos; descarga PyTorch y los modelos):

```bash
bash deploy/instalar.sh
```

5. Al final muestra la dirección, p. ej. `https://3-85-12-4.sslip.io`. Ábrela en
   Chrome o Edge. Usuario `cuidador`, clave `MenteEnMovimiento2026`.
   **Cambia esa clave** en `https://…/admin/` (o con `cd backend && .venv/bin/python manage.py changepassword cuidador`).

## 5. Comprobar que se usa AWS de verdad

- **RDS**: en el servidor, `grep DATABASE_URL backend/.env` muestra la URL de RDS; en la
  consola de RDS, *Monitoring* → *DB connections* sube al usar la app.
- **S3**: sube una foto en *Mi Historia* y aparece en el bucket, en `mi-historia/paciente_N/`.
- **Microservicio**: `curl http://127.0.0.1:8001/salud` en el servidor responde `{"estado":"ok",...}`.

## Día a día en AWS Academy

- La sesión del laboratorio dura 4 horas; al terminar, EC2 y RDS se apagan solos.
  Al pulsar **Start Lab** otra vez se encienden y la app arranca sola (servicios systemd).
- Sin Elastic IP la dirección cambia: vuelve a ejecutar `bash deploy/instalar.sh` y usa la nueva.
- Para publicar cambios del código:

```bash
cd /opt/mente && git pull && bash deploy/instalar.sh
```

- Registros: `sudo journalctl -u mente-backend -n 50`, `-u mente-vision`, `-u caddy`.

## Si algo falla

| Síntoma | Causa probable |
|---|---|
| La página no abre o da error de certificado | Faltan los puertos 80/443 en el grupo de seguridad, o pasaron menos de 1–2 minutos. Mira `sudo journalctl -u caddy -n 50`. |
| `could not connect to server` al instalar | RDS no está *Available* o no se eligió *Connect to an EC2 compute resource*. |
| Error `AccessDenied` al subir fotos | La instancia no tiene el rol **LabInstanceProfile** (EC2 → Actions → Security → Modify IAM role). |
| La instalación se corta por memoria | La instancia es menor que t3.medium. |
| No se ve la cámara | Se abrió por `http://` en vez de `https://`. |
