import requests
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials from environment variables
CLIENT_ID = os.getenv('ZOHO_CLIENT_ID')
CLIENT_SECRET = os.getenv('ZOHO_CLIENT_SECRET')
REDIRECT_URI = os.getenv('ZOHO_REDIRECT_URI')
AUTHORIZATION_CODE = os.getenv('ZOHO_AUTHORIZATION_CODE')

def generar_url_authorization():
    """
    Genera la URL para obtener un nuevo authorization code.
    """
    base_url = 'https://accounts.zoho.com/oauth/v2/auth'
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'Desk.tickets.CREATE,Desk.contacts.CREATE,Desk.basic.READ'
    }
    
    url = f"{base_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    print("\n=== PARA OBTENER UN NUEVO AUTHORIZATION CODE ===")
    print("1. Abre esta URL en tu navegador:")
    print(url)
    print("\n2. Autoriza la aplicación")
    print("3. Copia el código de la URL de redirección")
    print("4. Actualiza AUTHORIZATION_CODE en este script")
    print("===============================================\n")
    
    return url

def obtener_tokens_desde_code(client_id, client_secret, redirect_uri, code):
    """
    Intercambia un authorization code (Self Client) por access_token y refresh_token.
    """
    url = 'https://accounts.zoho.com/oauth/v2/token'
    data = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code
    }
    print(f"Enviando solicitud de token a: {url}")
    print(f"Datos enviados: {data}")
    
    resp = requests.post(url, data=data)
    
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    
    datos = resp.json()
    print(f"Respuesta de la API: {datos}")
    
    if 'access_token' not in datos:
        print("Error: No se recibió access_token en la respuesta")
        print(f"Respuesta completa: {datos}")
        raise KeyError("access_token no encontrado en la respuesta")
    
    return datos['access_token'], datos['refresh_token']

def refrescar_access_token(client_id, client_secret, refresh_token):
    """
    Renueva el access_token usando un refresh_token.
    """
    url = 'https://accounts.zoho.com/oauth/v2/token'
    params = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    return resp.json()['access_token']

def obtener_org_id(access_token):
    """
    Obtiene el ID de la primera organización disponible en Zoho Desk.
    """
    url = 'https://desk.zoho.com/api/v1/organizations'
    headers = {'Authorization': f'Zoho-oauthtoken {access_token}'}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json().get('data', [])
    return data[0]['id'] if data else None

def listar_departamentos(access_token, org_id):
    """
    Lista todos los departamentos disponibles en la organización.
    """
    url = 'https://desk.zoho.com/api/v1/departments'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'orgId': str(org_id)
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json().get('data', [])
    
    print("\n=== DEPARTAMENTOS DISPONIBLES ===")
    for dept in data:
        print(f"ID: {dept['id']} | Nombre: {dept['name']} | Email: {dept.get('email', 'N/A')}")
    print("================================\n")
    
    return data

def crear_contacto_simple(access_token, org_id, email, nombre='Cliente Prueba'):
    """
    Crea un contacto simple en Zoho Desk.
    """
    url = 'https://desk.zoho.com/api/v1/contacts'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'orgId': str(org_id),
        'Content-Type': 'application/json'
    }
    
    payload = {
        'firstName': nombre.split()[0] if ' ' in nombre else nombre,
        'lastName': nombre.split()[1] if ' ' in nombre else '',
        'email': email
    }
    
    print(f"Creando contacto con payload: {payload}")
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    
    contacto = resp.json()
    print(f"Contacto creado: {contacto['firstName']} {contacto['lastName']} (ID: {contacto['id']})")
    return contacto['id']

def crear_ticket(access_token, org_id, subject, department_id, contact_id, descripcion=''):
    url = 'https://desk.zoho.com/api/v1/tickets'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'orgId': str(org_id),
        'Content-Type': 'application/json'
    }
    payload = {
        'subject': subject,
        'departmentId': department_id,
        'contactId': contact_id
    }
    if descripcion:
        payload['description'] = descripcion
    
    print(f"Enviando payload: {payload}")
    
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        print(f"Headers enviados: {headers}")
        resp.raise_for_status()
    
    ticket = resp.json()
    return ticket.get('id') or ticket.get('ticketId')

def obtener_estado_ticket(access_token, org_id, ticket_id):
    url = f'https://desk.zoho.com/api/v1/tickets/{ticket_id}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'orgId': str(org_id)
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get('statusType')

def main():
    print("Iniciando script de Zoho Desk API...")
    print(f"CLIENT_ID: {CLIENT_ID}")
    print(f"REDIRECT_URI: {REDIRECT_URI}")
    print(f"AUTHORIZATION_CODE: {AUTHORIZATION_CODE[:20]}...")
    
    # 1. Intercambiar el código por tokens iniciales
    print("Obteniendo tokens...")
    try:
        access_token, refresh_token = obtener_tokens_desde_code(
            CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, AUTHORIZATION_CODE
        )
        print(f'Access token inicial: {access_token}')
    except KeyError as e:
        if "access_token no encontrado" in str(e):
            print("\n❌ El authorization code ha expirado o es inválido.")
            generar_url_authorization()
            return
        else:
            raise e

    # 2. Obtener el orgId
    org_id = obtener_org_id(access_token)
    print(f'OrgId: {org_id}')

    # 3. Listar departamentos disponibles
    departamentos = listar_departamentos(access_token, org_id)
    
    if not departamentos:
        print("No se encontraron departamentos. No se puede crear el ticket.")
        return
    
    # Usar el primer departamento disponible
    department_id = departamentos[0]['id']
    print(f"Usando departamento: {departamentos[0]['name']} (ID: {department_id})")
    
    # 4. Crear un contacto para el ticket
    email_cliente = 'cliente@ejemplo.com'
    contact_id = crear_contacto_simple(access_token, org_id, email_cliente)
    
    # 5. Crear un ticket de prueba
    ticket_id = crear_ticket(
        access_token, org_id,
        subject='Prueba API Self Client',
        department_id=department_id,
        contact_id=contact_id,
        descripcion='Ticket de prueba creado con Self Client.'
    )
    print(f'Ticket creado con ID: {ticket_id}')

    # 4. Vigilar el estado del ticket (renovando token si es necesario)
    while True:
        try:
            estado = obtener_estado_ticket(access_token, org_id, ticket_id)
            print(f'Estado actual: {estado}')
            if estado == 'Closed':
                print('El ticket se ha cerrado')
                break
        except requests.HTTPError as e:
            # Si obtenemos un 401 Unauthorized, es posible que el access_token haya expirado
            print('El token expiró, renovando…', e)
            access_token = refrescar_access_token(CLIENT_ID, CLIENT_SECRET, refresh_token)
        time.sleep(60)

if __name__ == '__main__':
    main()
