"""Windows RAW receipts. No browser rendering, arbitrary commands, or sale mutations.

Spooler acceptance does not prove paper output. The API commits a claim BEFORE
calling this module and never automatically resends an uncertain job.
"""
import os
import ctypes as ct
from ctypes import wintypes as wt
from decimal import Decimal
import textwrap
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def clean(value):
    # User-entered names/references must never inject ESC/POS control bytes.
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'replace').decode('ascii')
    return ''.join(c if 32 <= ord(c) < 127 else ' ' for c in value)


def receipt_bytes(sale, columns=48, mode='escpos', cut=False, timezone_name='Africa/Nairobi'):
    lines = []
    def write(value):
        lines.extend(textwrap.wrap(clean(value), width=columns) or [''])
    def pair(label, amount):
        amount = f'{Decimal(str(amount)):,.2f}'
        label = clean(label)
        if len(label) + len(amount) + 1 > columns:
            write(label)
            lines.append(amount.rjust(columns))
        else:
            lines.append(label + ' ' * (columns-len(label)-len(amount)) + amount)
    if sale is None:
        write('DATUS - PRINTER TEST')
        write('NOT A SALE / NO PAYMENT REQUIRED')
        write('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        write('abcdefghijklmnopqrstuvwxyz 0123456789')
        pair('Test amount KES', '768')
        write('-' * columns)
        write(f'{columns} columns - {mode}')
    else:
        write(sale['business_name'])
        write('SALES RECEIPT / COPY')
        write(sale['number'])
        stamp = datetime.fromisoformat(sale['created_at'])
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        write(stamp.astimezone(ZoneInfo(timezone_name)).strftime('%Y-%m-%d %H:%M:%S %Z'))
        write('Customer: ' + sale['customer'])
        write('Served by: ' + sale['served_by'])
        write('Channel: ' + sale['transaction_type'])
        write('-' * columns)
        for item in sale['lines']:
            write(item['name'] + ' - ' + item['unit'])
            pair(f"{Decimal(item['quantity']).normalize():f} x {Decimal(item['unit_price']).normalize():f}", item['subtotal'])
            if Decimal(item['discount']):
                pair('Line discount (already deducted)', item['discount'])
        write('-' * columns)
        pair('Subtotal', sale['subtotal'])
        pair('Tax', sale['tax'])
        pair('TOTAL ' + sale['currency'], sale['total'])
        labels = {'cash':'Cash retained', 'external_mobile':'M-Pesa', 'external_bank':'Bank', 'external_card':'Card'}
        for payment in sale['payments']:
            pair(labels.get(payment['method'], payment['method']), payment['amount'])
            if payment.get('reference'):
                write('Reference: ' + payment['reference'])
        pair('Balance', sale['balance'])
        write('-' * columns)
        write('Thank you for shopping with us.')
        write('Powered by DATUS')
    payload = ('\r\n'.join(lines) + '\r\n\r\n\r\n\r\n').encode('ascii')
    # Initialize, Font A, normal size/alignment/emphasis. Text-only sends no escapes.
    if mode == 'escpos':
        payload = b'\x1b@\x1bM\x00\x1b!\x00\x1d!\x00\x1ba\x00\x1bE\x00' + payload
        if cut:
            payload += b'\x1dV\x00'
    return payload


def spooler():
    if os.name != 'nt':
        raise OSError('Direct printing requires the Windows shop server.')
    dll = ct.WinDLL('winspool.drv', use_last_error=True)
    specs = {
        'EnumPrintersW': ([wt.DWORD, wt.LPWSTR, wt.DWORD, ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD), ct.POINTER(wt.DWORD)], wt.BOOL),
        'OpenPrinterW': ([wt.LPWSTR, ct.POINTER(wt.HANDLE), ct.c_void_p], wt.BOOL),
        'StartDocPrinterW': ([wt.HANDLE, wt.DWORD, ct.c_void_p], wt.DWORD),
        'WritePrinter': ([wt.HANDLE, ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD)], wt.BOOL),
    }
    for name in ['StartPagePrinter', 'EndPagePrinter', 'EndDocPrinter', 'ClosePrinter', 'AbortPrinter']:
        specs[name] = ([wt.HANDLE], wt.BOOL)
    for name, (args, result) in specs.items():
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = args, result
    return dll


def printers():
    dll = spooler()
    needed, count = wt.DWORD(), wt.DWORD()
    ok = dll.EnumPrintersW(6, None, 4, None, 0, ct.byref(needed), ct.byref(count))
    if not ok and ct.get_last_error() != 122:  # ERROR_INSUFFICIENT_BUFFER
        raise ct.WinError(ct.get_last_error())
    if not needed.value:
        return []
    buffer = ct.create_string_buffer(needed.value)
    if not dll.EnumPrintersW(6, None, 4, buffer, len(buffer), ct.byref(needed), ct.byref(count)):
        raise ct.WinError(ct.get_last_error())
    class Info(ct.Structure):
        _fields_ = [('name', wt.LPWSTR), ('server', wt.LPWSTR), ('attributes', wt.DWORD)]
    rows = ct.cast(buffer, ct.POINTER(Info))
    return sorted({rows[i].name for i in range(count.value) if rows[i].name})


def send_raw(printer, payload, title):
    dll, handle = spooler(), wt.HANDLE()
    class Doc(ct.Structure):
        _fields_ = [('name', wt.LPWSTR), ('output', wt.LPWSTR), ('datatype', wt.LPWSTR)]
    def check(value):
        if not value:
            raise ct.WinError(ct.get_last_error())
        return value
    check(dll.OpenPrinterW(printer, ct.byref(handle), None))
    started = False
    try:
        doc = Doc(title, None, 'RAW')
        job = check(dll.StartDocPrinterW(handle, 1, ct.byref(doc)))
        started = True
        check(dll.StartPagePrinter(handle))
        buffer = ct.create_string_buffer(payload)
        written = wt.DWORD()
        check(dll.WritePrinter(handle, buffer, len(payload), ct.byref(written)))
        if written.value != len(payload):
            raise OSError('Incomplete spooler write')
        check(dll.EndPagePrinter(handle))
        check(dll.EndDocPrinter(handle))
        started = False
        return job
    finally:
        if started:
            dll.AbortPrinter(handle)
        dll.ClosePrinter(handle)
