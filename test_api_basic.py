import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(endpoint, method="GET", data=None):
    url = f"{BASE_URL}{endpoint}"
    print(f"\nTesting endpoint: {url} with method {method}")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            print(f"Method {method} not supported in this test script")
            return
            
        print(f"Status code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text[:300])
        else:
            print(response.text[:300])
    except Exception as e:
        print(f"Error: {e}")

# Test available plans
print("\n=== Testing Public Endpoints ===")
test_endpoint("/api/plans/")

# Test classes (should be unauthorized)
test_endpoint("/api/classes/")

# Test activities
test_endpoint("/api/activities/")

print("\nAPI Basic Testing completed") 