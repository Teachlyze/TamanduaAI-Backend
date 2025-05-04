import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# Tenta criar um usuário de teste
def test_register():
    print("\nTesting register endpoint...")
    url = f"{BASE_URL}/api/auth/register/"
    data = {
        "email": "teste@example.com",
        "password": "senha123",
        "password_confirmation": "senha123",
        "first_name": "Usuário",
        "last_name": "Teste",
        "full_name": "Usuário Teste Completo",
        "cpf": "12345678900"  # CPF fictício para teste
    }
    
    try:
        print(f"Sending data to {url}: {json.dumps(data)}")
        response = requests.post(url, json=data)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 201
    except Exception as e:
        print(f"Error: {e}")
        return False

# Tenta login com o usuário criado
def test_login():
    print("\nTesting login endpoint...")
    url = f"{BASE_URL}/api/auth/login/"
    data = {
        "email": "teste@example.com",
        "password": "senha123"
    }
    
    try:
        print(f"Sending data to {url}: {json.dumps(data)}")
        response = requests.post(url, json=data)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            # Obtém o token para uso futuro
            token = response.json().get('token', '')
            if token:
                print(f"Authenticated successfully! Token: {token[:10]}...")
                return token
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Testa endpoint protegido com o token
def test_protected_endpoint(token):
    if not token:
        print("\nSkipping protected endpoint test - no token available")
        return
        
    print("\nTesting protected endpoint (users)...")
    url = f"{BASE_URL}/api/users/"
    headers = {
        'Authorization': f'Token {token}'
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        if response.status_code == 200:
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text)
        else:
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

# Executa os testes
registered = test_register()
token = test_login()
test_protected_endpoint(token)

print("\nAuthentication Testing completed") 