# Zoho Desk API Client

Cliente para la API de Zoho Desk usando Self Client para autenticación OAuth2.

## Instalación

### Usando uv (recomendado)

```bash
# Instalar dependencias
uv sync

# Ejecutar el script
uv run prueba.py
```

### Usando pip

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el script
python prueba.py
```

## Configuración

Antes de ejecutar el script, asegúrate de:

1. Tener configurado tu Self Client en Zoho Developer Console
2. Actualizar las credenciales en `prueba.py`:
   - `CLIENT_ID`
   - `CLIENT_SECRET`
   - `AUTHORIZATION_CODE`
   - `department_id` (ID del departamento donde crear tickets)

## Funcionalidades

- Autenticación OAuth2 con Self Client
- Creación de tickets en Zoho Desk
- Monitoreo del estado de tickets
- Renovación automática de tokens de acceso 