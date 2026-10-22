"""Gera o django.mo a partir do django.po sem precisar do gettext (msgfmt) instalado.

Uso, a partir de backend/:  python locale/build_mo.py
Rodar de novo sempre que editar locale/es/LC_MESSAGES/django.po.
"""
import ast
import struct
from pathlib import Path

PO = Path(__file__).resolve().parent / "es" / "LC_MESSAGES" / "django.po"


def parse(po_text):
    entries, msgid, msgstr, current = {}, None, None, None
    for raw in po_text.splitlines() + [""]:
        line = raw.strip()
        if line.startswith("msgid "):
            if msgid is not None:
                entries[msgid] = msgstr
            msgid, msgstr, current = ast.literal_eval(line[6:]), "", "id"
        elif line.startswith("msgstr "):
            msgstr, current = ast.literal_eval(line[7:]), "str"
        elif line.startswith('"') and current:
            if current == "id":
                msgid += ast.literal_eval(line)
            else:
                msgstr += ast.literal_eval(line)
        elif not line and msgid is not None:
            entries[msgid] = msgstr
            msgid, current = None, None
    return {k: v for k, v in entries.items() if v or k == ""}


def write_mo(entries, path):
    keys = sorted(entries)
    ids = b"".join(k.encode() + b"\0" for k in keys)
    strs = b"".join(entries[k].encode() + b"\0" for k in keys)
    n = len(keys)
    start = 7 * 4 + 16 * n
    offsets, o = [], 0
    for k in keys:
        offsets.append((len(k.encode()), start + o))
        o += len(k.encode()) + 1
    soffsets, o = [], 0
    for k in keys:
        soffsets.append((len(entries[k].encode()), start + len(ids) + o))
        o += len(entries[k].encode()) + 1
    header = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + 8 * n, 0, 0)
    table = b"".join(struct.pack("ii", *x) for x in offsets) + b"".join(struct.pack("ii", *x) for x in soffsets)
    path.write_bytes(header + table + ids + strs)


if __name__ == "__main__":
    data = parse(PO.read_text(encoding="utf-8"))
    write_mo(data, PO.with_suffix(".mo"))
    print(f"{len(data) - 1} traducciones -> {PO.with_suffix('.mo')}")
