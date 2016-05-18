#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com
import sys, os
import locale
from cStringIO import StringIO
import Tkinter
from tkFileDialog import askopenfilenames, askdirectory, asksaveasfilename
from ScrolledText import ScrolledText
import fb2utils.validation
from fb2utils.validation import do_process_file
from fb2utils.utils import LogOptions, walk
from lxml import _elementpath
import gzip

class options:
    html = False
    quiet = False
fb2utils.validation.options = options

class markup:
    h2 = 'h2'
    h3 = 'h3'
    h4 = 'h4'
    good = 'good'
    bad = 'bad'
    err = 'err'
    hr = '-'*72
fb2utils.validation.markup = markup

enc = locale.getpreferredencoding()
nfile = 1
def process_file(filename):
    # process one file
    global nfile
    errors, output = do_process_file(filename)
    if errors or not options.quiet:
        for s in output:
            tag = None
            mark = float(text.index("end"))-1
            if isinstance(s, tuple):
                if s[1] == markup.h2:
                    txt = '%d. %s' % (nfile, s[0])
                    tag = 'h2'
                    nfile += 1
                elif s[1] == markup.h3:
                    txt = s[0]
                    tag = 'h3'
                elif s[1] == markup.h4:
                    txt = s[0]
                    tag = 'h4'
                elif s[1] == markup.good:
                    txt = s[0]
                    tag = 'good'
                elif s[1] == markup.bad:
                    txt = s[0]
                    tag = 'bad'
                else:
                    txt = s[1][0]+s[0]+s[1][1]
            else:
                txt = s
            txt = txt+'\n'
            if isinstance(txt, str):
                txt = unicode(txt, enc)
            text['state'] = 'normal'
            text.insert('end', txt)
            text['state'] = 'disabled'
            end = float(text.index("end"))-1
            if tag is not None:
                text.tag_add(tag, mark, end)
#             else:
#                 text.tag_add('txt', mark, end)

    text.update_idletasks()
    text.update()
    return errors

def run(fn):
    global nfile
    nfile = 1
    LogOptions.outfile = StringIO()
    button_open_file['state'] = 'disabled'
    button_open_dir['state'] = 'disabled'
    button_quiet['state'] = 'disabled'
    button_close['state'] = 'disabled'
    text['state'] = 'normal'
    text.delete(0.0, 'end')
    text['state'] = 'disabled'
    text['cursor'] = 'watch'
    try:
        for f in walk(fn):
            process_file(f)
    finally:
        button_open_file['state'] = 'normal'
        button_open_dir['state'] = 'normal'
        button_quiet['state'] = 'normal'
        button_close['state'] = 'normal'
        text['cursor'] = ''


initialdir = None
def open_file():
    global initialdir
    fn = askopenfilenames(initialdir=initialdir)
    if fn:
        initialdir = os.path.dirname(fn[0])
        try:
            run(fn)
        except Tkinter.TclError:
            pass

def open_dir():
    global initialdir
    fn = askdirectory(initialdir=initialdir)
    if fn:
        initialdir = fn
        try:
            run(fn)
        except Tkinter.TclError:
            pass

def save_log():
    fn = asksaveasfilename()
    if fn:
        txt = text.get(0.0, 'end')
        enc = locale.getpreferredencoding()
        open(fn, 'wt').write(txt.encode(enc))

def quiet():
    options.quiet = quiet_var.get()


LogOptions.level = 0

font  = '{Courier New} 12'
font_bold = font+' bold'
root = Tkinter.Tk()
root.title('FB2 validator')
button_open_file = Tkinter.Button(root, text='Open files...',
                                  width=11, command=open_file)
button_open_file.grid(column=0, row=0)
button_open_dir = Tkinter.Button(root, text='Open dir...',
                                 width=11, command=open_dir)
button_open_dir.grid(column=1, row=0)
quiet_var = Tkinter.BooleanVar()
button_quiet = Tkinter.Checkbutton(root, text='Quiet', width=11,
                                   command=quiet, indicatoron=False,
                                   variable=quiet_var)
button_quiet.grid(column=2, row=0, sticky='ns')
button_close = Tkinter.Button(root, text='Close', width=11, command=root.quit)
button_close.grid(column=3, row=0, sticky='e')
text = ScrolledText(root, state='disabled',
                    font=font, exportselection=True)
text.grid(column=0, row=1, columnspan=4, sticky='news')
text.tag_config('h2', foreground='blue', font=font_bold)
text.tag_config('h3', foreground='blue')
text.tag_config('h4', font=font_bold)
text.tag_config('good', foreground='#00a000')
text.tag_config('bad', foreground='red')
text.tag_config('txt', background='#e8e8e8')
root.columnconfigure(3, weight=999)
root.rowconfigure(1, weight=999)

def select_all():
    text.tag_remove('sel', 0.0, 'end')
    text.tag_add('sel', 0.0, 'end')

def text_copy():
    #text.event_generate("<<Copy>>")
    text.tk.call("tk_textCopy", text)

def make_menu(w):
    global the_menu
    the_menu = Tkinter.Menu(w, tearoff=0)
    the_menu.add_command(label="Select all", command=select_all)
    the_menu.add_command(label="Copy", command=text_copy)
    the_menu.add_command(label="Save log...", command=save_log)

def show_menu(e):
    w = e.widget
    the_menu.tk.call("tk_popup", the_menu, e.x_root, e.y_root)

make_menu(root)
text.bind_class("Text", "<Button-3><ButtonRelease-3>", show_menu)

root.mainloop()

