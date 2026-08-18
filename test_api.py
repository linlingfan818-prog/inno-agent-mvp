import httpx
import json
import os

url = "https://api.llm-incubator.automotive.cloud/dev/v0/llm/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer gAAAAABp_CRLGlBaxx2o7G0jDefnCWDXCBoI7Etaop5o4f4AEE-e-2oQwyDyibN7CPY6pDOpYwBma4VjyRin8oz18OJTn6mBw_eb7o7xs2O8QBvjsad3fZ6Jsavn4iDD4qaEGJZDzoJ8pQXXIJyCaE6KNetuKE97SA==",
    "X-Application-Token": "gAAAAABqg_M4mT1C3vxGp0xfmj2j4PiNefq_8DtWy3Fbgmh6aLL0Ab4y1z6AWCWsEcoCfpVCJZu68Kcbzk0v0ZM210bUXL1yapVg2mGyVHjpEMqSnjO3GuA="
}
data = {
    "model": "claude-4-6-opus-v1:0",
    "messages": [{"role": "user", "content": "Hello, test"}]
}

print("Testing API from Python...")
try:
    with httpx.Client(verify=False) as client:
        response = client.post(url, headers=headers, json=data, timeout=30.0)
        print(f"Status Code: {response.status_code}")
        try:
            print("Response:", json.dumps(response.json(), indent=2, ensure_ascii=False))
        except Exception:
            print("Raw Response:", response.text)
except Exception as e:
    print("Error:", e)
