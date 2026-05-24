"""
End-to-end upload test: sends the synthetic WAV to the running backend.
Usage: uv run python test_audio/test_upload.py
"""
import json
import sys
import os
import urllib.request
import urllib.error

API_BASE = "http://127.0.0.1:8001"

def test_health_check():
    print("=== Test 1: Health Check ===")
    try:
        req = urllib.request.urlopen(f"{API_BASE}/")
        data = json.loads(req.read())
        print(f"  [OK] Server healthy: {data}")
        return True
    except Exception as e:
        print(f"  [FAIL] Server not reachable: {e}")
        return False

def test_upload(wav_path, expect_pass=True):
    print(f"\n=== Test: Upload {os.path.basename(wav_path)} (expect {'PASS' if expect_pass else 'REJECT'}) ===")
    
    if not os.path.exists(wav_path):
        print(f"  [SKIP] File not found: {wav_path}")
        return
    
    # Build multipart form data manually
    boundary = "----MockingBirdTestBoundary"
    
    metadata = json.dumps({
        "lat": 27.7172,
        "lon": 85.3240,
        "altitude_m": 1400,
        "recorded_at": "2026-05-23T09:00:00Z",
        "user_id": "00000000-0000-0000-0000-000000000000"
    })
    
    with open(wav_path, "rb") as f:
        audio_data = f.read()
    
    body = b""
    # Audio file part
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="audio"; filename="{os.path.basename(wav_path)}"\r\n'.encode()
    body += b"Content-Type: audio/wav\r\n\r\n"
    body += audio_data
    body += b"\r\n"
    # Metadata part
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="metadata"\r\n\r\n'
    body += metadata.encode()
    body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    
    req = urllib.request.Request(
        f"{API_BASE}/recordings/upload",
        data=body,
        headers=headers,
        method="POST"
    )
    
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"  [OK] Status: {resp.status}")
        print(f"  Health Score: {data.get('health_score')}")
        print(f"  Components: {json.dumps(data.get('components', {}), indent=4)}")
        print(f"  Species ({len(data.get('species', []))}): ", end="")
        for s in data.get("species", []):
            endemic_tag = " [ENDEMIC]" if s.get("is_endemic") else ""
            print(f"\n    - {s['common_name']} ({s['scientific_name']}) conf={s['confidence_raw']:.2f}{endemic_tag}", end="")
        print()
        if data.get("explanation"):
            print(f"  Explanation:")
            for k, v in data["explanation"].items():
                print(f"    {k}: {v}")
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode()
        if e.code == 422 and not expect_pass:
            print(f"  [OK] Correctly rejected (422): {resp_body}")
        else:
            print(f"  [{'OK' if not expect_pass else 'FAIL'}] HTTP {e.code}: {resp_body}")
    except Exception as e:
        print(f"  [FAIL] Error: {e}")

def test_map_pins():
    print("\n=== Test: Map Pins ===")
    try:
        req = urllib.request.urlopen(f"{API_BASE}/map/pins")
        data = json.loads(req.read())
        pins = data.get("pins", [])
        print(f"  [OK] {len(pins)} pins on map")
        for p in pins[:5]:
            print(f"    Pin: score={p['health_score']}, endemic={p.get('has_endemic')}, "
                  f"({p['latitude']:.3f}, {p['longitude']:.3f})")
    except Exception as e:
        print(f"  [FAIL] {e}")

if __name__ == "__main__":
    if not test_health_check():
        print("\nServer is not running. Start it first:")
        print("  uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000")
        sys.exit(1)
    
    # Test real file (should pass)
    test_upload("test_audio/XC944110 - Identity unknown.wav", expect_pass=True)
    
    # Test 15s file (should be rejected by quality gate)
    test_upload("test_audio/too_short_15s.wav", expect_pass=False)
    
    # Test map pins
    test_map_pins()
    
    print("\n=== All tests complete ===")
