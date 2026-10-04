"""Makes Career_Hub_Guide.pdf (for Harshitha) from docs/Career_Hub_Guide.docx (the source you edit).

    python tools/make_guide.py

Uses Microsoft Word on Windows, or LibreOffice (soffice) anywhere. Run it before every release, after the docs are updated.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from careerhub.config import APP_VERSION          # noqa: E402

SRC = ROOT / "docs" / "Career_Hub_Guide.docx"
OUT = ROOT / "Career_Hub_Guide.pdf"


def docx_version():
    """The 'vX.Y' written in the page header of the .docx."""
    with zipfile.ZipFile(SRC) as z:
        for name in z.namelist():
            if name.startswith("word/header"):
                m = re.search(r"Guide \(v([\d.]+)\)", re.sub(r"<[^>]+>", "", z.read(name).decode("utf-8")))
                if m:
                    return m.group(1)
    return None


def with_word(src, out):
    ps = ("$w = New-Object -ComObject Word.Application; $w.Visible = $false; try { "
          f"$d = $w.Documents.Open('{src}', $false, $true); $d.SaveAs2('{out}', 17); $d.Close($false) "
          "} finally { $w.Quit() }")
    return subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).returncode == 0 and out.exists()


def with_soffice(src, outdir):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return False
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src)], capture_output=True)
    return (outdir / (src.stem + ".pdf")).exists()


def main():
    if not SRC.exists():
        sys.exit(f"Missing {SRC}")
    v = docx_version()
    if v != APP_VERSION:
        sys.exit(f"The guide header says v{v} but the app is v{APP_VERSION}. Update the guide (header and content) first.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        out = tmp / "guide.pdf"
        ok = (sys.platform == "win32" and with_word(str(SRC), out)) or False
        if not ok:
            ok = with_soffice(SRC, tmp)
            out = tmp / (SRC.stem + ".pdf")
        if not ok:
            sys.exit("Couldn't make the PDF: needs Microsoft Word (Windows) or LibreOffice installed.")
        shutil.copyfile(out, OUT)
    print(f"{OUT.name} written from {SRC.name} (v{v})")


if __name__ == "__main__":
    main()
