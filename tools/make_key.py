#!/usr/bin/env python3
"""Make the release signing key:  python3 tools/make_key.py [--out FILE]

Writes a new private key (default ~/.careerhub_release_key, readable only by you) and prints its public half.
Never overwrites an existing key. To rotate: make the new key with --out, put its public half in PUBLIC_KEY
(careerhub/sigcheck.py), ship ONE release signed with the OLD key, and only then switch to the new key.
Back the private key up (password manager + an offline copy): if it is lost, her app refuses all updates.
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from careerhub import sigcheck


def main():
    args = sys.argv[1:]
    out = Path(args[args.index("--out") + 1]).expanduser() if "--out" in args else Path.home() / ".careerhub_release_key"
    if out.exists():
        sys.exit(f"{out} already exists, not overwriting it. Use --out for a new file.")
    seed = secrets.token_bytes(32)
    out.write_text(seed.hex(), encoding="ascii")
    if os.name == "nt":
        subprocess.run(["icacls", str(out), "/inheritance:r", "/grant:r", f"{os.environ.get('USERNAME')}:R"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        out.chmod(0o600)
    pub = sigcheck.public_key(seed).hex()
    print(f"Private key written to {out}  (back it up, never commit it)")
    print(f"Public key:  {pub}")
    print("Put the public key in PUBLIC_KEY in careerhub/sigcheck.py" + ("" if pub != sigcheck.PUBLIC_KEY else " (already there)"))


if __name__ == "__main__":
    main()
