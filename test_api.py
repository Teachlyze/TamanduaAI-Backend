import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(endpoint):
    url = f"{BASE_URL}{endpoint}"
    print(f"\nTesting endpoint: {url}")
    try:
        response = requests.get(url)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
        else:
            print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
    except Exception as e:
        print(f"Error: {e}")

# Test root API endpoint
test_endpoint("/api/")

# Test auth endpoints
test_endpoint("/api/auth/register/")
test_endpoint("/api/auth/login/")

# Test users endpoint
test_endpoint("/api/users/")

# Test plans endpoint
test_endpoint("/api/plans/")

# Test classes endpoint
test_endpoint("/api/classes/")

print("\nAPI Testing completed") 