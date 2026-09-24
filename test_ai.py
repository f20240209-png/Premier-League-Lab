"""Optional live AI smoke test, only executed explicitly."""
import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("Set GEMINI_API_KEY locally first.")
        return 1
    from google import genai
    with genai.Client(api_key=key) as client:
        response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents="Reply with: Connection successful")
    print(response.text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
