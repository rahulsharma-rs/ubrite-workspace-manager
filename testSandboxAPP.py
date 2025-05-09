import requests, json
token ="""eyJhbGciOiJSUzI1NiIsImtpZCI6InB1YmxpYzpkNzE0M2RiMy03M2RlLTRlM2YtODMxNS0xNmVmMjI1MjIxMjIiLCJ0eXAiOiJKV1QifQ.eyJhdWQiOlsiZGF0YWxlbnMtZGV2LmhzLnVhYi5lZHUiLCJkYXRhbGVucy1xYS5ocy51YWIuZWR1IiwiZGF0YWxlbnMuaHMudWFiLmVkdSIsImRhdGFsZW5zLXRlc3QuaHMudWFiLmVkdSJdLCJjbGllbnRfaWQiOiJkYXRhbGVucyIsImV4cCI6MTc0Njc1MzMzMSwiZXh0Ijp7fSwiaWF0IjoxNzQ2NzUxNTMxLCJpc3MiOiJodHRwczovL3NlcnZpY2VzLmlkbS51YWIuZWR1L2F1dGgvcHVibGljLyIsImp0aSI6ImUxYjQ2ZjQwLThmODItNGI4Yi1hOGUzLTk3ZmY0NDdmYWQ1NiIsIm5iZiI6MTc0Njc1MTUzMSwic2NwIjpbIm9wZW5pZCJdLCJzdWIiOiJyc2hhcm1hM0B1YWIuZWR1In0.NaRqgrgveBB2rQY_M4WmHPNq7X3pD5ipTOEM8uvnTq-GUVr80e-b2Ph4arYNvdHkCrsKXmmYaMmgPS4UvNBfxOIte3qeXAby7Hk1v4L49kZHwsAw4jAylwWIYXKAFwl0t--odwdxfDghS40FctfSIA5ItC99ytVL4d612C-DRt5hrbSUaHK5LonR_oWqBffY1f_KrxKSXcDWz5kPge3SqhV-R7TOVliZg0OCyYb1gMdIdQZHpOj2TEq64IjTTwQiCf1kq16Z3GdOozpXu3Sn1BqsTr6N0Yb6Mr8Ze8dZ6-RvjpHVfRy9cqrQEDbx3J_FqFR5LrcueT62D6Nem0weLX6d9kgtZciFaMdVNYl7aJquWxjvzM1OXLp9QrEy4UWw9sg8uc5XYnd6z94zC834gKpEh32nOoueEP3sAXk3LFtDHFllmGzNtKbA8eRmWE963_JnqLtuAa3YUTEzyPvCsFyP0gF6GL51ym9ke-Fcewrr6iZPRz2CTpnV9I1t7IrjTe9nueB9aQDiOpvsEaeizWiRfCX7bvmqILyVCRgGCXeJYGOZAOQNFlKrw0zJOenzrARXAvMXwfKXKxsDsPvqfB3IkCq6MOlwuw3cv63vgkhPkNCjhSm1HbQIz52E8Lv0Y-xqsN8W041-dMfPk87EvVQBaQDPkI7zGFxY8bAWPU0"""
BASE = "https://rc.uab.edu/pun/dev/cohort_eda_api_project"
#!/usr/bin/env python3
"""
simple_list_test.py

A minimal script to call the `/list` endpoint of your OnDemand Passenger Flask API
at https://rc.uab.edu/pun/dev/cohort_eda_api_project.

Usage:
  export OOD_TOKEN=<your_personal_access_token>
  python simple_list_test.py
"""

import os
import sys
import requests

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BASE_URL = "https://rc.uab.edu/pun/dev/cohort_eda_api_project"
#TOKEN    = os.getenv(token)
# ────────────────────────────────────────────────────────────────────────────────

# if not TOKEN:
#     print("Error: Please set the OOD_TOKEN environment variable.", file=sys.stderr)
#     sys.exit(1)

HEADERS = {"Authorization": f"Bearer {token}"}

def list_files():
    url = f"{BASE_URL}/list"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        print("Error: Response was not valid JSON:", resp.text, file=sys.stderr)
        sys.exit(1)

    files = data.get("files", [])
    if not files:
        print("No files returned.")
    else:
        print("Files on server:")
        for f in files:
            print("  -", f)

if __name__ == "__main__":
    list_files()

    print("x")