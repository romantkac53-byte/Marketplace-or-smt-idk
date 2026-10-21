"""Сборка django.mo из django.po без GNU gettext (у Windows его обычно нет).

    python locale/build_mo.py
Поддерживает простые записи msgid/msgstr (без множественных форм и контекстов) — этого достаточно для проекта.
"""
import ast
import struct
from pathlib import Path


def parse_po(text):
    entries, key, current = {}, None, {'msgid': [], 'msgstr': []}
    for line in text.splitlines() + ['']:
        line = line.strip()
        if line.startswith('msgid '):
            if current['msgstr']:
                entries[''.join(current['msgid'])] = ''.join(current['msgstr'])
            current, key = {'msgid': [], 'msgstr': []}, 'msgid'
            current[key].append(ast.literal_eval(line[6:]))
        elif line.startswith('msgstr '):
            key = 'msgstr'
            current[key].append(ast.literal_eval(line[7:]))
        elif line.startswith('"') and key:
            current[key].append(ast.literal_eval(line))
        elif not line and current['msgstr']:
            entries[''.join(current['msgid'])] = ''.join(current['msgstr'])
            current, key = {'msgid': [], 'msgstr': []}, None
    return entries


def write_mo(entries, path):
    keys = sorted(entries)
    ids = [k.encode('utf-8') for k in keys]
    strs = [entries[k].encode('utf-8') for k in keys]
    header = 7 * 4
    orig_table, trans_table = header, header + len(keys) * 8
    offset = trans_table + len(keys) * 8
    orig, trans, data = [], [], b''
    for s in ids:
        orig.append((len(s), offset + len(data))); data += s + b'\0'
    for s in strs:
        trans.append((len(s), offset + len(data))); data += s + b'\0'
    out = struct.pack('<7I', 0x950412DE, 0, len(keys), orig_table, trans_table, 0, 0)
    out += b''.join(struct.pack('<2I', *x) for x in orig) + b''.join(struct.pack('<2I', *x) for x in trans) + data
    Path(path).write_bytes(out)


if __name__ == '__main__':
    for po in Path(__file__).parent.glob('*/LC_MESSAGES/*.po'):
        entries = parse_po(po.read_text(encoding='utf-8'))
        write_mo(entries, po.with_suffix('.mo'))
        print(f'{po.with_suffix(".mo")}: {len(entries) - 1} перевод(ов)')
