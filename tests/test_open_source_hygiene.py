"""Fails when a secret, a private file, a local username or a personal name comes back into the tree.

Forbidden words are stored as sha256 hashes so the test itself does not carry them. Add a word:
    python3 -c "import hashlib;print(hashlib.sha256(b'word').hexdigest())"
"""
import hashlib
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# sha256 of lowercase words that must never appear in a tracked text file
FORBIDDEN_WORD_HASHES = {
    "0cf4027c098909ffc3e4cf0d3581bd72e7af26bf403f0200516a196e2118389e",
    "a4e463d7dec930ea7f5a7d92fc3b798a167c7c206438739d4c82d96d5ebf2cfe",
    "32e24af0b13bb87451da5ce0680db55391c2d588a2ab6efbe226a1c2234413dc",
}

# files that must never be tracked (exact paths or prefixes)
FORBIDDEN_TRACKED = [
    ".env",
    "deploy/npm-recovery-codes.txt",
    "deploy/mcp-registry/key.pem",
    "deploy/mcp-registry/privkey.hex",
    "data/",
    "docs/BILLING.md", "docs/STRIPE.md", "docs/LEMONSQUEEZY.md", "docs/BUSINESS.md",
]

# files that must not exist on disk inside the repo at all (they belong in a private directory)
FORBIDDEN_ON_DISK = [
    "deploy/npm-recovery-codes.txt",
]

# token shapes; placeholders such as sk_live_... are shorter than the minimum length
SECRET_PATTERNS = [
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{16,}"),          # Stripe
    re.compile(r"whsec_[A-Za-z0-9+/=]{24,}"),                 # Stripe / Polar webhook secret
    re.compile(r"polar_(oat|pat)_[A-Za-z0-9_]{16,}"),         # Polar
    re.compile(r"\bre_[A-Za-z0-9]{28,}"),                     # Resend
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),              # GitHub
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}"),                    # npm
    re.compile(r"\bpypi-[A-Za-z0-9_-]{40,}"),                 # PyPI
    re.compile(r"\bxox[abpr]-[0-9]{8,}-[A-Za-z0-9-]{10,}"),   # Slack
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                      # AWS
    re.compile(r"\b[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}"),        # Telegram bot token
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"/home/[a-z0-9_-]+/"),                        # local absolute paths
    re.compile(r"[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook|proton|protonmail|icloud|live)\.[a-z]{2,}"),
]

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".tgz", ".db", ".pdf")
SKIP_NAMES = ("package-lock.json",)
SKIP_DIRS = (".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "data", "dist")


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        files = [f for f in out.decode().split("\0") if f]
        if files:
            return files
    except Exception:
        pass
    files = []
    for d, dirs, names in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for n in names:
            files.append(os.path.relpath(os.path.join(d, n), ROOT))
    return files


def text_files():
    for f in tracked_files():
        if f.endswith(SKIP_SUFFIXES) or os.path.basename(f) in SKIP_NAMES:
            continue
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        try:
            yield f, open(p, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue


def test_no_forbidden_files_tracked():
    bad = [f for f in tracked_files() if any(f == x or (x.endswith("/") and f.startswith(x)) for x in FORBIDDEN_TRACKED)]
    assert not bad, f"private files are tracked: {bad}"


def test_no_forbidden_files_on_disk():
    bad = [f for f in FORBIDDEN_ON_DISK if os.path.exists(os.path.join(ROOT, f))]
    assert not bad, f"move these to a private directory outside the repo: {bad}"


def test_gitignore_keeps_private_files_out():
    ignore = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().splitlines()
    for needed in (".env", "data/", "deploy/npm-recovery-codes.txt", "deploy/mcp-registry/key.pem", "deploy/mcp-registry/privkey.hex"):
        assert needed in ignore, f".gitignore lost the entry {needed}"


def test_no_secret_shapes_in_tracked_files():
    hits = []
    for f, s in text_files():
        for pat in SECRET_PATTERNS:
            m = pat.search(s)
            if m:
                hits.append((f, m.group(0)[:12] + "..."))
    assert not hits, f"secret-looking strings in tracked files: {hits}"


def test_no_forbidden_words_in_tracked_files():
    word_re = re.compile(r"[a-z0-9]+")
    hits = []
    for f, s in text_files():
        for w in set(word_re.findall(s.lower())):
            if hashlib.sha256(w.encode()).hexdigest() in FORBIDDEN_WORD_HASHES:
                hits.append((f, w[:2] + "*" * (len(w) - 2)))
    assert not hits, f"forbidden username or personal name in tracked files: {hits}"


def test_env_example_lists_every_variable_server_reads():
    src = open(os.path.join(ROOT, "runvouch", "server.py"), encoding="utf-8").read()
    used = set(re.findall(r'os\.(?:getenv|environ\.get)\(\s*"([A-Z_]+)"', src)) - {"AGENTWATCH_NO_SWEEP"}
    example = open(os.path.join(ROOT, ".env.example"), encoding="utf-8").read()
    listed = set(re.findall(r"^#?([A-Z_]+)=", example, re.M))
    missing = sorted(used - listed)
    assert not missing, f"add to .env.example: {missing}"
