"""Graphical first-run wizard and local-server controller. Packaged as DATUS.exe."""
import argparse
import ctypes
import hashlib
import json
import os
import queue
import sys
import threading
import webbrowser
from pathlib import Path

from datus.paths import data_root
from desktop.runtime import Installation, VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true', help='Verify packaged resources without installing or changing user data')
    parser.add_argument('--smoke-test', metavar='EMPTY_DIRECTORY', help='Run isolated first setup, sale, backup and shutdown checks')
    args = parser.parse_args()
    if args.self_test:
        from desktop.smoke import resource_check
        resource_check()
        return
    if args.smoke_test:
        from desktop.smoke import smoke_test
        smoke_test(Path(args.smoke_test))
        return

    import tkinter as tk
    from tkinter import ttk, messagebox
    data = data_root()
    data.mkdir(parents=True, exist_ok=True)
    (data / 'logs').mkdir(exist_ok=True)
    # Windowed executables have no console streams. Alembic and diagnostic logs need one.
    log = (data / 'logs' / 'application.log').open('a', encoding='utf-8')
    if sys.stdout is None: sys.stdout = log
    if sys.stderr is None: sys.stderr = log
    mutex = None
    if os.name == 'nt':
        name = 'Local\\DATUS-Desktop'
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        mutex = kernel.CreateMutexW(None, False, name)
        if not mutex: raise RuntimeError('Cannot create the DATUS instance lock.')
        if ctypes.get_last_error() == 183:
            settings_file = data / 'database-admin.json'
            if settings_file.exists():
                settings = json.loads(settings_file.read_text(encoding='utf-8'))
                webbrowser.open(f'http://127.0.0.1:{settings["http_port"]}')
            return

    root = tk.Tk()
    root.title(f'DATUS {VERSION} — Retail & Wholesale')
    root.geometry('550x480'); root.minsize(500, 450)
    root.configure(bg='#f5f6f2')
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background='#f5f6f2')
    style.configure('TLabel', background='#f5f6f2', foreground='#183b34', font=('Segoe UI', 10))
    style.configure('Title.TLabel', font=('Segoe UI', 24, 'bold'))
    style.configure('TButton', padding=9, font=('Segoe UI', 10))
    frame = ttk.Frame(root, padding=28); frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='DATUS', style='Title.TLabel').pack(anchor='w')
    ttk.Label(frame, text='Your shop. Every detail, accounted for.').pack(anchor='w', pady=(2, 20))
    form = ttk.Frame(frame); form.pack(fill='x')
    installation = Installation()
    events = queue.Queue()
    status = tk.StringVar(value='Create your shop owner account to get started.' if not installation.marker.exists() else 'Starting your local workspace…')
    busy = False
    fields = {}

    def worker(action, success):
        nonlocal busy
        if busy: return
        busy = True
        def run():
            try: action(); events.put(('ok', success))
            except Exception as error:
                # Log only type; never dump connection strings, SQL parameters or passwords.
                print(f'Desktop action failed: {type(error).__name__}', file=log, flush=True)
                message = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'The operation could not complete. Check the local logs and configuration. Your business data was preserved.'
                events.put(('error', message))
        threading.Thread(target=run, daemon=True).start()

    def start():
        values = {name: field.get().strip() if name != 'password' and name != 'confirm' else field.get() for name, field in fields.items()}
        if fields:
            if not values['business'] or not values['username'] or len(values['username']) > 80 or len(values['business']) > 160:
                messagebox.showerror('Check your details', 'Enter a shop name (up to 160 characters) and username (up to 80).'); return
            if len(values['password']) < 12 or values['password'] != values['confirm']:
                messagebox.showerror('Check your password', 'Use at least 12 characters and enter the same password twice.'); return
        status.set('Preparing the local database and workspace. First setup may take a minute…')
        def initialize():
            installation.initialize(values.get('business', 'DATUS'), values.get('username'), values.get('password'))
            installation.start_server()
        worker(initialize, 'started')

    def ready():
        for child in form.winfo_children(): child.destroy()
        fields.clear()
        ttk.Label(form, text='Your local workspace is running.').pack(anchor='w', pady=(0, 12))
        ttk.Button(form, text='Open DATUS', command=lambda: webbrowser.open(installation.address)).pack(fill='x', pady=5)
        ttk.Button(form, text='Create encrypted backup', command=lambda: worker(installation.backup, 'backup')).pack(fill='x', pady=5)
        ttk.Button(form, text='Open data and backups folder', command=lambda: os.startfile(str(data))).pack(fill='x', pady=5)
        ttk.Label(form, text='Keep this window open while trading.\nClosing it safely stops DATUS and its private database.', wraplength=440).pack(anchor='w', pady=15)
        webbrowser.open(installation.address)

    def close():
        if busy:
            messagebox.showinfo('Please wait', 'Wait for the current setup or backup operation to finish.'); return
        if not messagebox.askyesno('Close DATUS?', 'Finish any checkout first. Close DATUS and stop its local database?'): return
        status.set('Stopping DATUS safely…')
        worker(installation.stop, 'closed')

    def poll():
        nonlocal busy
        try:
            kind, result = events.get_nowait(); busy = False
            if kind == 'error': status.set(result); messagebox.showerror('DATUS needs attention', result)
            elif result == 'started': status.set('Ready · ' + installation.address); ready()
            elif result == 'backup': status.set('Encrypted backup created in the backups folder.')
            elif result == 'closed': root.destroy(); return
        except queue.Empty: pass
        root.after(150, poll)

    if not installation.marker.exists():
        for name, label in [('business', 'Shop name'), ('username', 'Owner username'), ('password', 'Password · at least 12 characters'), ('confirm', 'Confirm password')]:
            ttk.Label(form, text=label).pack(anchor='w', pady=(4, 2))
            field = ttk.Entry(form, show='*' if name in ('password', 'confirm') else '')
            field.pack(fill='x'); fields[name] = field
        ttk.Button(form, text='Create shop and open DATUS', command=start).pack(fill='x', pady=16)
    else:
        ttk.Button(form, text='Retry startup', command=start).pack(fill='x')
        root.after(100, start)
    ttk.Label(frame, textvariable=status, wraplength=470).pack(anchor='w', pady=14)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(150, poll)
    root.mainloop()
    if mutex: kernel.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if '--smoke-test' in sys.argv or '--self-test' in sys.argv:
            # Automated jobs must fail, not hang waiting for a windowed crash dialog.
            if '--self-test' in sys.argv:
                import traceback
                Path(sys.executable).with_name('self-test-failure.log').write_text(traceback.format_exc(), encoding='utf-8')
            if '--smoke-test' in sys.argv:
                destination = Path(sys.argv[sys.argv.index('--smoke-test') + 1])
                if destination.is_dir():
                    import traceback
                    frames = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name} for f in traceback.extract_tb(error.__traceback__)]
                    (destination / 'smoke-failure.json').write_text(json.dumps({'error_type': type(error).__name__, 'frames': frames}), encoding='utf-8')
            raise SystemExit(1)
        raise
