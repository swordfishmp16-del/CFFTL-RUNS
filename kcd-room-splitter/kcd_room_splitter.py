"""KCD ROOM SPLITTER

Splits a multi-room KCD job into one job file per room, named
"<job number> <last name> <room name from the sidebar>.job", and saves them in
C:\\KCD ROOM SPLITTER\\<job number> <last name>\\ together with a split report.

Open the program and choose a job, or drag a .job file onto the program's icon.
For testing it also runs without a window:
    "KCD ROOM SPLITTER.exe" --cli JOBFILE --job 1080458 --name NOTIK [--out DIR] [--replace]
                            [--check-only] [--log FILE]
"""
import argparse
import os
import sys
import traceback

import kcdsplit

TITLE = kcdsplit.APP_NAME


# ---------------------------------------------------------------------------------------
# without a window (testing)

def run_cli(argv):
    ap = argparse.ArgumentParser(prog=TITLE)
    ap.add_argument('--cli', action='store_true')
    ap.add_argument('job_file')
    ap.add_argument('--job', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--out', default=kcdsplit.OUT_ROOT)
    ap.add_argument('--replace', action='store_true')
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--log')
    a = ap.parse_args(argv)
    lines = []
    code = 0
    try:
        if a.check_only:
            job, files, job_flags = kcdsplit.check_job(a.job_file, a.job, a.name)
            lines.append('CHECKED %d rooms -> %d files (nothing saved)' % (job.n, len(files)))
            flags = job_flags + [(lvl, '%s: %s' % (f['name'], m)) for f in files for lvl, m in f['flags']]
        else:
            res = kcdsplit.split_job(a.job_file, a.job, a.name, a.out, a.replace)
            files = res['files']
            lines.append('SAVED %d files in %s' % (len(files), res['folder']))
            lines.append('REPORT %s' % res['report'])
            flags = kcdsplit.all_flags(res)
        for f in files:
            lines.append('FILE %s | rooms %s | walls %d | cabinets %d | notes %d | %s'
                         % (f['file'], f['rooms'], f['walls'], f['cabinets'], f['notes'], f.get('md5', '')))
        lines += ['%s %s' % (lvl, m) for lvl, m in flags]
    except kcdsplit.SplitError as e:
        lines.append('STOPPED %s' % e)
        code = 1
    except Exception:
        lines.append('ERROR ' + traceback.format_exc())
        code = 2
    out = '\n'.join(lines)
    print(out)
    if a.log:
        with open(a.log, 'w', encoding='utf-8') as fh:
            fh.write(out + '\n')
    return code


# ---------------------------------------------------------------------------------------
# the window

def run_gui(start_path=None):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(TITLE)
    root.geometry('1060x680')
    root.minsize(820, 520)
    try:
        ttk.Style().theme_use('vista')
    except tk.TclError:
        pass

    state = {'path': None, 'job': None, 'folder': None}
    job_no = tk.StringVar()
    last_name = tk.StringVar()
    dest = tk.StringVar(value='')
    status = tk.StringVar(value='Choose a KCD job to split.')
    file_label = tk.StringVar(value='No job chosen yet.')

    root.columnconfigure(0, weight=1)
    root.rowconfigure(4, weight=3)
    root.rowconfigure(5, weight=1)

    head = ttk.Frame(root, padding=(14, 12, 14, 4))
    head.grid(row=0, column=0, sticky='ew')
    ttk.Label(head, text=TITLE, font=('Segoe UI', 18, 'bold')).pack(anchor='w')
    ttk.Label(head, text='Makes one KCD file per room, named with the job number, last name and the '
                         'room name from the sidebar.').pack(anchor='w')

    pick = ttk.Frame(root, padding=(14, 6))
    pick.grid(row=1, column=0, sticky='ew')
    pick.columnconfigure(1, weight=1)
    ttk.Button(pick, text='Choose KCD job...', command=lambda: choose()).grid(row=0, column=0, sticky='w')
    ttk.Label(pick, textvariable=file_label).grid(row=0, column=1, sticky='w', padx=10)

    form = ttk.Frame(root, padding=(14, 4))
    form.grid(row=2, column=0, sticky='ew')
    ttk.Label(form, text='Job number').grid(row=0, column=0, sticky='w')
    e_job = ttk.Entry(form, textvariable=job_no, width=14, font=('Segoe UI', 11))
    e_job.grid(row=0, column=1, sticky='w', padx=(6, 20))
    ttk.Label(form, text='Customer last name').grid(row=0, column=2, sticky='w')
    e_name = ttk.Entry(form, textvariable=last_name, width=22, font=('Segoe UI', 11))
    e_name.grid(row=0, column=3, sticky='w', padx=6)

    ttk.Label(root, textvariable=dest, padding=(14, 2)).grid(row=3, column=0, sticky='ew')

    table = ttk.Frame(root, padding=(14, 4))
    table.grid(row=4, column=0, sticky='nsew')
    table.columnconfigure(0, weight=1)
    table.rowconfigure(0, weight=1)
    cols = ('file', 'walls', 'cabinets', 'notes', 'flags')
    tree = ttk.Treeview(table, columns=cols, show='headings', height=12)
    for c, label, w, anchor in (('file', 'Room file (name from the sidebar)', 520, 'w'), ('walls', 'Walls', 60, 'center'),
                                ('cabinets', 'Cabinets', 70, 'center'), ('notes', 'Notes', 60, 'center'),
                                ('flags', 'Flags', 220, 'w')):
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anchor, stretch=(c == 'file'))
    tree.tag_configure('check', background='#ffe3b3')
    sb = ttk.Scrollbar(table, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.grid(row=0, column=0, sticky='nsew')
    sb.grid(row=0, column=1, sticky='ns')

    fl = ttk.Frame(root, padding=(14, 4))
    fl.grid(row=5, column=0, sticky='nsew')
    fl.columnconfigure(0, weight=1)
    fl.rowconfigure(1, weight=1)
    ttk.Label(fl, text='Flags (CHECK = look at this before using the file, NOTE = for your information)').grid(
        row=0, column=0, sticky='w')
    flags_box = tk.Text(fl, height=7, wrap='word', font=('Segoe UI', 10), relief='solid', borderwidth=1)
    flags_box.grid(row=1, column=0, sticky='nsew')
    fsb = ttk.Scrollbar(fl, orient='vertical', command=flags_box.yview)
    flags_box.configure(yscrollcommand=fsb.set, state='disabled')
    fsb.grid(row=1, column=1, sticky='ns')
    flags_box.tag_configure('CHECK', foreground='#b34700', font=('Segoe UI', 10, 'bold'))
    flags_box.tag_configure('NOTE', foreground='#555555')
    flags_box.tag_configure('OK', foreground='#1d6b2a', font=('Segoe UI', 10, 'bold'))

    bar = ttk.Frame(root, padding=(14, 8, 14, 12))
    bar.grid(row=6, column=0, sticky='ew')
    bar.columnconfigure(2, weight=1)
    b_split = tk.Button(bar, text='SPLIT ROOMS', font=('Segoe UI', 12, 'bold'), bg='#1f5f99', fg='white',
                        activebackground='#174a78', activeforeground='white', padx=18, pady=4,
                        state='disabled', command=lambda: split())
    b_split.grid(row=0, column=0, sticky='w')
    b_open = ttk.Button(bar, text='Open folder', state='disabled', command=lambda: open_folder())
    b_open.grid(row=0, column=1, sticky='w', padx=10)
    ttk.Label(bar, textvariable=status).grid(row=0, column=2, sticky='w', padx=6)

    def show_flags(items, done_msg=None):
        flags_box.configure(state='normal')
        flags_box.delete('1.0', 'end')
        if done_msg:
            flags_box.insert('end', done_msg + '\n', 'OK')
        if not items:
            flags_box.insert('end', 'No flags.\n', 'NOTE')
        for lvl, msg in items:
            flags_box.insert('end', '%-6s ' % lvl, lvl)
            flags_box.insert('end', msg + '\n')
        flags_box.configure(state='disabled')

    def current_plan(preview=True):
        jn, nm = job_no.get().strip(), last_name.get().strip()
        if preview:
            jn, nm = jn or '#######', nm or 'NAME'
        return kcdsplit.plan(state['job'], jn, nm)

    def refresh(*_):
        tree.delete(*tree.get_children())
        if not state['job']:
            return
        try:
            files, job_flags = current_plan()
        except kcdsplit.SplitError as e:
            show_flags([(kcdsplit.CHECK, str(e))])
            b_split.configure(state='disabled')
            return
        for f in files:
            n_check = sum(1 for lvl, _ in f['flags'] if lvl == kcdsplit.CHECK)
            n_note = len(f['flags']) - n_check
            txt = ', '.join(x for x in ('%d to check' % n_check if n_check else '',
                                        '%d note' % n_note if n_note else '') if x)
            tree.insert('', 'end', values=(f['file'], f['walls'], f['cabinets'], f['notes'], txt),
                        tags=('check',) if n_check else ())
        items = job_flags + [(lvl, '%s: %s' % (f['name'], m)) for f in files for lvl, m in f['flags']]
        show_flags(sorted(items, key=lambda x: x[0] != kcdsplit.CHECK))
        ready = bool(job_no.get().strip() and last_name.get().strip())
        folder = kcdsplit.job_folder(kcdsplit.OUT_ROOT, job_no.get() or '#######', last_name.get() or 'NAME')
        dest.set('Room files will be saved in:  %s' % folder)
        b_split.configure(state='normal' if ready else 'disabled')
        status.set('%d rooms in the job, %d room files. %s' % (
            state['job'].n, len(files), '' if ready else 'Type the job number and last name.'))

    job_no.trace_add('write', refresh)
    last_name.trace_add('write', refresh)

    def load(path):
        state.update(path=None, job=None, folder=None)
        b_open.configure(state='disabled')
        tree.delete(*tree.get_children())
        status.set('Reading the job...')
        root.update_idletasks()
        try:
            job = kcdsplit.Job(open(path, 'rb').read())
        except kcdsplit.SplitError as e:
            file_label.set(os.path.basename(path))
            show_flags([(kcdsplit.CHECK, str(e))])
            status.set('This job cannot be split.')
            b_split.configure(state='disabled')
            return
        except OSError as e:
            messagebox.showerror(TITLE, 'The job file could not be opened.\n\n%s' % e)
            status.set('Choose a KCD job to split.')
            return
        state.update(path=path, job=job)
        file_label.set(path)
        jn, nm = kcdsplit.guess_job_and_name(path, job)
        if jn and not job_no.get().strip():
            job_no.set(jn)
        if nm and not last_name.get().strip():
            last_name.set(nm)
        refresh()
        (e_job if not job_no.get().strip() else e_name).focus_set()

    def choose():
        p = filedialog.askopenfilename(title='Choose the KCD job to split',
                                       filetypes=[('KCD job', '*.job'), ('All files', '*.*')])
        if p:
            job_no.set('')
            last_name.set('')
            load(p)

    def split():
        if not state['job']:
            return
        try:
            files, _ = current_plan(preview=False)
        except kcdsplit.SplitError as e:
            messagebox.showwarning(TITLE, str(e))
            return
        folder = kcdsplit.job_folder(kcdsplit.OUT_ROOT, job_no.get(), last_name.get())
        there = kcdsplit.existing_files(files, folder)
        if there and not messagebox.askyesno(
                TITLE, 'Room files for this job are already in\n%s\n\nReplace them with new ones?' % folder):
            return
        b_split.configure(state='disabled')

        def progress(msg):
            status.set(msg)
            root.update()
        root.config(cursor='watch')
        try:
            res = kcdsplit.split_job(state['path'], job_no.get(), last_name.get(), kcdsplit.OUT_ROOT,
                                     replace=bool(there), progress=progress)
        except kcdsplit.SplitError as e:
            status.set('Stopped. Nothing was made.')
            messagebox.showerror(TITLE, str(e))
            return
        except Exception:
            status.set('Stopped.')
            messagebox.showerror(TITLE, 'Something went wrong. Nothing should be used from this run.\n\n'
                                        + traceback.format_exc(limit=3))
            return
        finally:
            root.config(cursor='')
            b_split.configure(state='normal')
        state['folder'] = res['folder']
        b_open.configure(state='normal')
        flags = kcdsplit.all_flags(res)
        n_check = sum(1 for lvl, _ in flags if lvl == kcdsplit.CHECK)
        done = 'Done. %d room files saved and double-checked in %s' % (len(res['files']), res['folder'])
        show_flags(flags, done)
        status.set('Done. %d room files saved.' % len(res['files']))
        messagebox.showinfo(TITLE, '%s\n\n%s' % (done, '%d item(s) flagged to check. See the list.' % n_check
                                                  if n_check else 'Nothing was flagged to check.'))

    def open_folder():
        if state['folder'] and os.path.isdir(state['folder']):
            os.startfile(state['folder'])

    if start_path:
        root.after(100, lambda: load(start_path))
    root.mainloop()


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == '--cli':
        return run_cli(argv)
    run_gui(argv[0] if argv else None)
    return 0


if __name__ == '__main__':
    sys.exit(main())
