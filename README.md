# Doxxx

<p align="center">
  <img src="https://github.com/user-attachments/assets/49ec8d24-665b-4115-8525-01a8d0ca2ef4" alt="Doxxx Logo" width="600" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.5.2.5-blueviolet?style=for-the-badge&logo=github" />
  <img src="https://img.shields.io/pepy/dt/doxxx?style=for-the-badge" />
  <a href="https://discord.gg/tVNrKVXb49" target="_blank">
     <img src="https://img.shields.io/badge/Discord-Join%20Chat-7289da?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://doxxx.app?utm_source=github&utm_medium=readme&utm_campaign=repo-badge" target="_blank">
     <img src="https://img.shields.io/badge/Web%20App-user--scanner.app-000000?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Web App" />
  </a>
</p>


<p align="center">
  <a href="https://trendshift.io/repositories/16556" target="_blank">
    <img src="https://trendshift.io/api/badge/repositories/16556" alt="kaifcodec%2Fdoxx | Trendshift" width="250" height="55"/>
  </a>
</p>

---

A powerful **2-in-1 OSINT suite** engineered for deep **Email and Username Intelligence**.

With **2720+ total scan vectors**—including **210+ email-integrated sites** and **2510+ username platforms**—you can map digital footprints, analyze target behavior, uncover interests, full metadata of usernames and verify account registrations in seconds.


---

<p align="center">
  🔍 <strong>Looking for Phone Number OSINT?</strong> Check out our other project <a href="https://github.com/kaifcodec/phonsint"><strong>phonsint</strong></a> to uncover accounts, masked emails, and profile photos with zero SMS alerts. 
  <a href="https://github.com/kaifcodec/phonsint"><strong>Explore phonsint →</strong></a>
</p>

## ✨ Key Features

- 🔎 **Deep Email & Username OSINT:** Look up email registrations and perform advanced username profiling across 2710+ platforms.
- 👤 **Rich Metadata Scraping:** Scrapes avatars, bio descriptions, follower counts, UID numbers, seller statuses, and account attributes.
- 🔀 **Cross-Scan & Pivot Engine:** Mines handles, profile links, and exposed email addresses from initial scans, automatically pivoting across secondary target vectors.
- 🤖 **Model Context Protocol (MCP) Server:** Native AI agent integration for Claude Desktop, Cursor, Antigravity, and LLMs to run autonomous OSINT scans and recursive pivots.
- 🛡️ **Hudson Rock Infostealer Breach Intel:** Query infostealer malware breach logs using the `--hudson` flag for high-priority target correlation.
- ⚡ **High-Throughput Parallel Engine:** Powered by `httpx` and `curl_cffi` for maximum concurrency with automated TLS fingerprint impersonation.
- 🔀 **Permutation & Alias Generator:** Wildcard-based username variation generation to catch typosquatting or alternative aliases.
- 📂 **Multi-Format Reports:** Automated exports to **PDF** (with profile photos), **JSON**, and **CSV** for pipeline integration.
- 🌐 **Advanced Proxy Pivoting:** Built-in proxy rotation with protocol auto-detection (`http`, `socks5`) and pre-scan reachability check (`--validate-proxies`).
- 🎨 **Responsive Terminal UI:** Dynamic progress tracking, self-adaptive category grids (`-lu`/`-le`), and clear status reporting.

---

## 🚀 Installation

### 🐍 Via PyPI (Recommended)

```bash
# Upgrade pip and install doxxx
python3 -m pip install --upgrade pip
pip install doxxx

# Optional: Install with MCP Server support for AI agents
pip install "doxxx[mcp]"
```

### 📦 Virtual Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install package
pip install doxxx
```

### ❄️ Via Nix (Linux & macOS)

```bash
# Run instantly without installing permanently
nix run github:NPCmillionaire/doxxx/main -- --help

# Drop into a temporary shell with doxxx active
nix shell github:NPCmillionaire/doxxx/main
```

---

## 💻 Usage Guide

### 1. Basic Username & Email Scanning

Scan a single username or email address across all available platform modules:

```bash
doxxx -u johndoe             # Single username scan
doxxx -e johndoe@gmail.com   # Single email scan
doxxx -u johndoe --email-domains global  # Try johndoe across provider domains
```

### 2. Cross-Scan & Pivot Intelligence

An email scan proves an account exists but rarely reveals a handle. `--cross-scan` mines exposed handles, profile links, and secondary email addresses from target profiles, pivoting into multi-pass reconnaissance across all matching platforms:

| Pivot Direction | What it Mines |
| :--- | :--- |
| `-e` → **username** | Handles or social links exposed on an email's registered profile |
| `-u` → **username** | Secondary aliases advertised across target social profiles |
| `-u` → **email** | Public email addresses published on target profile pages |
| `-e` → **email** | Secondary addresses exposed by initial email profiles |

```bash
doxxx -u johndoe --cross-scan                                  # Pivot from username scan
doxxx -e johndoe@gmail.com --cross-scan                        # Pivot from email scan
doxxx -e johndoe@gmail.com --cross-scan --cross-links verified # Platform-verified links only
doxxx -u johndoe --cross-scan --cross-depth 2        # Follow links two hops deep
```

> 💡 *For confidence scoring, link classification rules, and cost models, see **[docs/CROSS_SCAN.md](docs/CROSS_SCAN.md)**.*

### 3. Hudson Rock Malware Breach Intelligence

Check if a target username or email address has been exposed in **infostealer malware infection logs**:

```bash
doxxx -u johndoe --hudson             # Username malware log check
doxxx -e johndoe@gmail.com --hudson   # Email malware log check
```

> 🖼️ *To view output terminal screenshots and visual previews, see **[docs/EXAMPLES.md](docs/EXAMPLES.md)**.*

### 4. Targeted Category & Module Scanning

Scan specific categories or individual modules, or list available modules in a responsive grid:

```bash
doxxx -u johndoe -c dev                # Developer platforms only
doxxx -e johndoe@gmail.com -m github   # Single module check
doxxx -u johndoe -m github,instagram   # Specific comma-separated modules

doxxx -lu                              # List user categories & modules grid
doxxx -le                              # List email categories & modules grid
```

### 5. Bulk File Scanning

Scan multiple targets from an input file (one target per line):

```bash
doxxx -uf usernames.txt   # Bulk username scan
doxxx -ef emails.txt      # Bulk email scan
```

### 6. Report Exports, Options & Proxies

```bash
# Export results to PDF, JSON, or CSV
doxxx -u johndoe -f pdf -o report.pdf
doxxx -u johndoe -f json -o results.json

# Verbose URL reporting and show all results (including not found)
doxxx -u johndoe -v --all

# Rotate proxies with a pre-scan reachability check
doxxx -u johndoe -P proxies.txt --validate-proxies
```

### 7. AI & LLM Agent Integration (MCP Server)

Connect `doxxx` directly to AI coding assistants and LLM platforms via the **Model Context Protocol (MCP)**. This enables AI agents (Claude Desktop, Cursor, Antigravity, Open-WebUI) to autonomously investigate handles and emails, pivot on exposed profiles, and analyze digital footprints.

#### Starting the Server

```bash
# Start the MCP server over standard I/O (stdio)
doxxx-mcp

# Optional: Enable verbose logging to stderr
doxxx-mcp -v
```

#### MCP Client Configuration

Add `doxxx` to your client configuration (e.g. `claude_desktop_config.json` or `mcp_config.json`):

```json
{
  "mcpServers": {
    "doxxx": {
      "command": "doxxx-mcp"
    }
  }
}
```

#### Exposed AI Tools

| Tool | Description | Capabilities |
| :--- | :--- | :--- |
| `scan_username` | Deep username OSINT & profile enrichment across platforms | Targeted scans (`category`, `module`), recursive `cross_scan`, proxy injection, loudness toggles |
| `scan_email` | Deep email verification & account discovery across platforms | Target scoping, automated link pivoting (`cross_scan`), custom proxies, loudness toggles |
| `list_available_modules` | Dynamic catalog & module discovery | Allows AI agents to query all supported platforms and categories dynamically |

An unknown `category` or `module` name is rejected with an error that suggests the closest valid names, so a typo never comes back as a scan with no findings. Use `list_available_modules` to see the full catalog.

---

## 📚 Documentation Hub

Explore detailed documentation guides in the [`docs/`](docs/) directory:

- 📋 **[CLI Flags Reference](docs/FLAGS.md)** — Complete breakdown of every CLI flag and option.
- 🔀 **[Cross-Scan & Pivoting Guide](docs/CROSS_SCAN.md)** — In-depth guide to multi-pass cross-scan reconnaissance.
- 🔀 **[Pattern Syntax Guide](docs/PATTERNS.md)** — Wildcard and permutation patterns for username generation.
- 🐍 **[Library Mode Guide](docs/USAGE.md)** — Calling the Python engine programmatically from your own scripts.
- 🌐 **[Proxy & Network Guide](docs/PROXIES.md)** — Proxy rotation formats, health checks, and regional VPN troubleshooting.
- 🖼️ **[Media & Output Gallery](docs/EXAMPLES.md)** — Video demonstrations, terminal recordings, and screenshot previews.

---

## 🐍 Python Library Mode

Integrate the Doxxx engine directly into your Python scripts:

```python
import asyncio
from doxxx.core import engine
from doxxx.email_scan.shopping import etsy

async def main():
    # Engine validates target against module and returns Result object
    result = await engine.check(etsy, "test@gmail.com")
    print(result.to_json())

asyncio.run(main())
```

> 💡 *For complete Python API documentation and batch category checking examples, see **[docs/USAGE.md](docs/USAGE.md)**.*


---


## 📜 Contributing

We welcome community contributions! Please read our **[Contributing Guidelines](CONTRIBUTING.md)** before opening a PR or submitting new scan modules.

---

## ⚠️ Disclaimer

This tool is provided strictly for **educational purposes**, **authorized security research**, and **defensive OSINT investigations**. The developers assume no liability and are not responsible for any misuse, unintended consequences, or legal actions resulting from the deployment of this software.
