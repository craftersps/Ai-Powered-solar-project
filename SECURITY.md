# Security Policy

## Supported Versions

The following versions of Environmental Monitor Pro are currently supported with security updates:

| Version | Supported                |
|---------|--------------------------| 
| 4.x (current) | ✅ Active support |
| 3.x | ⚠️ Critical fixes only      |
| < 3.0 | ❌ No longer supported    |

> This project runs as a **local network application** — the Flask server binds to `localhost:5000` and is not intended to be exposed to the public internet. The attack surface is limited to your local machine and LAN.

---

## Known Security Considerations

Because this is a local IoT dashboard, the main risks to be aware of are:

**Serial port access** — `server.py` opens a serial port to read from the Arduino. On Linux/Mac, ensure the port permissions are correctly set (`dialout` group) and avoid running the server as root.

**No authentication** — The dashboard has no login system by design (local use only). If you expose the server beyond `localhost`, add authentication middleware or use a reverse proxy like nginx with HTTP Basic Auth.

**Ollama CORS** — Starting Ollama with `OLLAMA_ORIGINS=*` allows any page on your machine to call it. This is fine for local use. Do not run Ollama this way on a shared or public-facing server.

**SQLite database** — `sensor_data.db` contains your environmental readings. It is gitignored by default. Do not commit it or expose it via a public endpoint.

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly rather than opening a public GitHub issue.

### How to report

1. **Email** the maintainer directly at the address listed on the GitHub profile
2. **Include** in your report:
   - A clear description of the vulnerability
   - Steps to reproduce it
   - The potential impact
   - Your suggested fix (if any)
3. **Use the subject line:** `[SECURITY] Environmental Monitor Pro — <brief description>`

### What to expect

| Timeline | Action |
|----------|--------|
| Within **48 hours** | Acknowledgement of your report |
| Within **7 days** | Initial assessment and severity classification |
| Within **30 days** | Patch released (or explanation if not applicable) |
| After fix is released | Public disclosure credit (if desired) |

We take all reports seriously. If the vulnerability is confirmed, we will credit you in the release notes unless you prefer to remain anonymous.

### What qualifies

Please report:
- Remote code execution possibilities
- Path traversal or file read vulnerabilities via the API
- Any way to escape the local network context unintentionally
- Dependency vulnerabilities with known CVEs (check `requirements.txt`)

The following are **out of scope** for this project:
- Attacks that require physical access to the machine running the server
- Issues only exploitable if the server is intentionally exposed to the public internet against the documentation's advice
- Social engineering

---

## Dependencies

You can audit the Python dependencies at any time:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

This will flag any known CVEs in `flask`, `pyserial`, or `requests`.
