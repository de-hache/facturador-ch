# 🚀 Manual de Procedimientos — Chuli-Facturador

**Repositorio:** `facturador-ch`  
**Usuario GitHub:** `de-hache`  
**Versión:** 1.0  
**Estado:** MVP funcional en homologación  
**Sistema operativo:** Windows 11  

> ⚠️ Este proyecto procesa información fiscal y datos personales. Nunca deben subirse a GitHub credenciales, certificados, bases de datos, logs ni archivos CSV reales.

---

## Índice

1. [Descripción del proyecto](#1-descripción-del-proyecto)
2. [Tecnologías utilizadas](#2-tecnologías-utilizadas)
3. [Estructura del proyecto](#3-estructura-del-proyecto)
4. [Instalación local](#4-instalación-local)
5. [Variables de entorno](#5-variables-de-entorno)
6. [Ejecución del sistema](#6-ejecución-del-sistema)
7. [Procesamiento de lotes](#7-procesamiento-de-lotes)
8. [Flujo de trabajo con Git](#8-flujo-de-trabajo-con-git)
9. [Ramas del proyecto](#9-ramas-del-proyecto)
10. [Commits y Pull Requests](#10-commits-y-pull-requests)
11. [Seguridad](#11-seguridad)
12. [Problemas frecuentes](#12-problemas-frecuentes)
13. [Checklist rápida](#13-checklist-rápida)

---

## 1. Descripción del proyecto

**Chuli-Facturador** es una aplicación web desarrollada con Python y FastAPI.

Su objetivo es procesar ventas exportadas en archivos CSV y emitir comprobantes electrónicos mediante los servicios de ARCA.

### Funcionalidades actuales

- Dashboard administrativo.
- Procesamiento de lotes CSV.
- Emisión de Factura C.
- Integración con ARCA en homologación.
- Registro de facturas en SQLite.
- Control de duplicados por número de orden.
- Reintentos automáticos ante errores temporales.
- Registro de eventos y errores.
- Gestión de operaciones pendientes.
- Reproceso manual de pendientes.
- Consulta de comprobantes emitidos.
- Configuración mediante variables de entorno.

---

## 2. Tecnologías utilizadas

| Tecnología | Uso |
|---|---|
| Python | Lenguaje principal |
| FastAPI | Servidor web y API |
| SQLite | Base de datos local |
| Pandas | Lectura y procesamiento de CSV |
| HTML | Interfaz del dashboard |
| CSS | Diseño visual |
| AFIP SDK | Comunicación con ARCA |
| Git | Control de versiones |
| GitHub | Repositorio remoto |

---

## 3. 📁 Estructura del proyecto

```text
Chuli-Facturador/
│
├── app/
│   ├── main.py
│   ├── database.py
│   └── logger.py
│
├── static/
│   └── css/
│       └── style.css
│
├── ventas/
│   └── archivos CSV locales
│
├── data/
│   └── facturador.db
│
├── logs/
│   └── registros locales
│
├── procesar_lote.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
└── MANUAL.md
```

### Archivos versionados en GitHub

```text
app/
static/
procesar_lote.py
requirements.txt
.env.example
.gitignore
README.md
MANUAL.md
LICENSE
```

### Archivos locales que no deben subirse

```text
.env
certificado.crt
privada.key
data/
logs/
ventas/
venv/
```

---

## 4. Instalación local

### 4.1. Clonar el repositorio

```bash
git clone https://github.com/laschescottas-cyber/Chuli-Facturador.git
```

Entrar en la carpeta:

```bash
cd Chuli-Facturador
```

### 4.2. Crear entorno virtual

```bash
python -m venv venv
```

Activarlo en Windows:

```bash
venv\Scripts\activate
```

Cuando esté activo, la terminal mostrará:

```text
(venv) PS C:\ruta\Chuli-Facturador>
```

### 4.3. Instalar dependencias

```bash
pip install -r requirements.txt
```

El archivo debe incluir:

```text
fastapi
uvicorn
python-multipart
pandas
requests
afip-py==1.2.0
python-dotenv
```

Verificar la instalación de AFIP SDK:

```bash
pip show afip-py
```

---

## 5. Variables de entorno

El archivo `.env` contiene la configuración real del sistema.

Debe crearse localmente copiando `.env.example`.

En PowerShell:

```bash
Copy-Item .env.example .env
```

Ejemplo de configuración:

```env
APP_NAME=Chuli-Facturador
APP_ENV=development
APP_DEBUG=True
APP_HOST=127.0.0.1
APP_PORT=8000

CUIT=XXXXXXXXXXX
AFIP_PRODUCTION=False
AFIP_ACCESS_TOKEN=TOKEN_REAL

AFIP_CERT_PATH=certificado.crt
AFIP_KEY_PATH=privada.key

PUNTO_VENTA=1
TIPO_COMPROBANTE=11

DATABASE_PATH=data/facturador.db
VENTAS_PATH=ventas
LOG_PATH=logs

ARCA_MAX_REINTENTOS=4
LOG_LEVEL=INFO
```

### `.env.example`

El archivo `.env.example` sí se sube a GitHub porque solo contiene valores de ejemplo.

### `.env`

El archivo `.env` no debe subirse porque contiene:

- CUIT real.
- Token de acceso.
- Rutas privadas.
- Configuración de producción.
- Credenciales del sistema.

Verificar que esté ignorado:

```bash
git check-ignore -v .env
```

---

## 6. Ejecución del sistema

Con el entorno virtual activo:

```bash
uvicorn app.main:app --reload
```

Abrir el dashboard:

```text
http://127.0.0.1:8000
```

Para detener el servidor:

```text
Ctrl + C
```

### Verificar estado del sistema

```text
http://127.0.0.1:8000/estado
```

### Consultar pantallas auxiliares

```text
http://127.0.0.1:8000/db/facturas
http://127.0.0.1:8000/db/eventos
http://127.0.0.1:8000/db/errores
```

---

## 7. Procesamiento de lotes

Los archivos CSV deben colocarse dentro de:

```text
ventas/
```

Nomenclatura recomendada:

```text
AAAA-MM-DD_a_AAAA-MM-DD.csv
```

Ejemplo:

```text
2026-07-01_a_2026-07-07.csv
```

El lote se selecciona desde el dashboard.

También puede ejecutarse manualmente:

```bash
python procesar_lote.py ventas/2026-07-01_a_2026-07-07.csv
```

### Control de duplicados

El sistema verifica el número de orden antes de emitir un comprobante.

Si la orden ya existe en SQLite, no se vuelve a facturar.

### Errores temporales

Ante errores de congestión, conexión o indisponibilidad de ARCA, el sistema realiza reintentos automáticos.

Si todos los intentos fallan, la orden queda registrada como pendiente.

---

## 8. Flujo de trabajo con Git

Antes de empezar cualquier cambio:

```bash
git checkout main
git pull origin main
```

Crear una rama nueva:

```bash
git checkout -b feature/nombre-del-cambio
```

Ejemplos:

```bash
git checkout -b feature/backups-sqlite
git checkout -b feature/github-actions
git checkout -b fix/lectura-csv
```

Revisar cambios:

```bash
git status
git diff
```

Agregar archivos:

```bash
git add .
```

Revisar qué se va a incluir:

```bash
git diff --cached --name-only
```

Crear commit:

```bash
git commit -m "Agrega backups automáticos de SQLite"
```

Subir la rama:

```bash
git push -u origin feature/backups-sqlite
```

---

## 9. Ramas del proyecto

### `main`

Contiene la versión estable.

No se debe desarrollar directamente sobre esta rama.

### `develop`

Contiene cambios integrados que todavía no fueron liberados a producción.

### `feature/...`

Se utiliza para nuevas funcionalidades.

Ejemplos:

```text
feature/github-actions
feature/logs-rotativos
feature/backups-sqlite
```

### `fix/...`

Se utiliza para corregir errores.

Ejemplos:

```text
fix/error-csv
fix/reintentos-arca
```

### `docs/...`

Se utiliza para documentación.

Ejemplo:

```text
docs/manual-procedimientos
```

---

## 10. Commits y Pull Requests

### Mensajes de commit recomendados

```text
Agrega reproceso manual de pendientes
Corrige lectura de archivos CSV
Mueve configuración a variables de entorno
Actualiza documentación de instalación
Agrega validaciones de seguridad
```

Evitar mensajes como:

```text
cambios
arreglo
prueba
final
cosas nuevas
```

### Crear Pull Request

Después de subir una rama:

1. Abrir el repositorio en GitHub.
2. Presionar **Compare & pull request**.
3. Escribir un título claro.
4. Describir los cambios.
5. Indicar cómo se probaron.
6. Crear el Pull Request.
7. Revisar antes de hacer merge.

Ejemplo:

```markdown
## Cambios

- Agrega backups automáticos de SQLite.
- Configura carpeta de respaldos.
- Registra eventos de backup.

## Pruebas

- Backup ejecutado localmente.
- Archivo SQLite generado correctamente.
- Se verificó que backups/ esté ignorado por Git.
```

---

## 11. ⚠️ Seguridad

Nunca subir a GitHub:

```text
.env
certificado.crt
privada.key
*.key
*.pem
*.csr
*.pfx
*.p12
data/facturador.db
logs/
ventas/*.csv
```

Los CSV pueden contener:

- Nombre y apellido.
- DNI.
- CUIT.
- Teléfono.
- Correo electrónico.
- Datos de compra.
- Información fiscal.

Antes de cada commit:

```bash
git diff --cached --name-only
```

Ver todos los archivos controlados por Git:

```bash
git ls-files
```

Buscar claves privadas:

```bash
git grep -n "BEGIN PRIVATE KEY"
```

Buscar certificados:

```bash
git grep -n "BEGIN CERTIFICATE"
```

No deberían devolver resultados.

### Si se sube un secreto por error

1. Revocar o reemplazar la credencial.
2. Retirar el archivo del seguimiento.
3. Crear un commit correctivo.
4. Revisar el historial.
5. Limpiar el historial si fuera necesario.

Eliminar el archivo en un commit posterior no borra el secreto de los commits anteriores.

---

## 12. Problemas frecuentes

### Git no se reconoce

```text
git no se reconoce como nombre de un cmdlet
```

Verificar:

```bash
git --version
```

Si no funciona, instalar Git for Windows y reiniciar Visual Studio Code.

### Remote origin ya existe

```text
error: remote origin already exists
```

Verificar:

```bash
git remote -v
```

Corregir:

```bash
git remote set-url origin https://github.com/laschescottas-cyber/Chuli-Facturador.git
```

### El remoto contiene cambios

```text
Updates were rejected because the remote contains work
```

Ejecutar:

```bash
git pull origin main --allow-unrelated-histories --no-edit
git push -u origin main
```

### Git abre Vim

Configurar VS Code:

```bash
git config --global core.editor "code --wait"
```

Configurar editor de secuencias:

```bash
git config --global sequence.editor "code --wait"
```

Evitar edición automática en merges:

```bash
git config --global merge.autoEdit no
```

### Archivo ignorado por error

Verificar:

```bash
git check-ignore -v app/main.py
```

Para ignorar solo el `main.py` de la raíz se usa:

```gitignore
/main.py
```

No usar:

```gitignore
main.py
```

porque también ignoraría `app/main.py`.

### Conflictos de merge

Revisar:

```bash
git status
```

Resolver las marcas:

```text
<<<<<<< HEAD
=======
>>>>>>> main
```

Después:

```bash
git add archivo.py
git commit -m "Resuelve conflicto de merge"
git push
```

Para cancelar:

```bash
git merge --abort
```

---

## 13. Checklist rápida

- [ ] Activar el entorno virtual.
- [ ] Ejecutar `git pull origin main`.
- [ ] Crear una rama `feature/`, `fix/` o `docs/`.
- [ ] Probar los cambios localmente.
- [ ] Revisar `git status`.
- [ ] Verificar `git diff --cached --name-only`.
- [ ] Confirmar que no haya datos sensibles.
- [ ] Crear un commit con mensaje claro.
- [ ] Subir la rama.
- [ ] Crear un Pull Request.