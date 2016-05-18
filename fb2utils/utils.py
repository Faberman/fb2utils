#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import sys
import os
import locale
import zipfile
import subprocess
from xml.sax.saxutils import escape
import traceback

##
##
##

prog_name = 'fb2utils'
prog_version = '0.6.1'

##
## Logging
##

class LogOptions:
    level = 1
    filename = None                     # name of processed file
    z_filename = None
    outfile = sys.stderr
    br = ''
    escape = False                      # escape html


def print_log(*s, **kw):
    # level: 0 - info, 1 - warning, 2 - error, 3 - fatal
    #enc = locale.getpreferredencoding()
    enc = 'utf-8'
    log_level = kw.get('level', 0)
    if log_level < LogOptions.level:
        return
    if LogOptions.filename:
        fn = (LogOptions.filename+':',)
        if LogOptions.z_filename:
            fn = (LogOptions.filename, '(%s):' % LogOptions.z_filename)
    else:
        fn = ()
    out = []
    for i in fn+s:
        if not i:
            continue
        if isinstance(i, unicode):
            out.append(i.encode(enc))
        else:
            out.append(i)
    s = ' '.join(out)
    if LogOptions.escape:
        s = escape(s)
    if LogOptions.br:
        s = s + LogOptions.br
    if isinstance(LogOptions.outfile, list):
        LogOptions.outfile.append(s)
    else:
        print >> LogOptions.outfile, s

##
##
##

def check_xml(data):
    ## BOM (Byte Order Mark)
    ## UTF-8: EF BB BF
    ## UTF-16BE: FE FF
    ## UTF-16LE: FF FE
    ## UTF-32BE: 00 00 FE FF
    ## UTF-32LE: FF FE 00 00
    for s in ('<?xml', '\xef\xbb\xbf<?xml',
              '\xff\xfe<\x00?\x00x\x00m\x00l\x00',
              '\xfe\xff\x00<\x00?\x00x\x00m\x00l',
              '\x00\x00\xff\xfe\x00\x00<\x00\x00\x00?\x00\x00\x00x\x00\x00\x00m\x00\x00\x00l\x00',
              '\xfe\xff\x00\x00\x00<\x00\x00\x00?\x00\x00\x00x\x00\x00\x00m\x00\x00\x00l\x00\x00'):
        if data.startswith(s):
            return True
    print_log('FATAL: file is not an XML file at all', level=3)
    return False


def print_exc():
    traceback.print_exc(file=LogOptions.outfile)

def count_files(arg):
    count = 0
    for fn in walk(arg):
        if zipfile.is_zipfile(fn):
            zf = zipfile.ZipFile(fn)
            count += len(zf.namelist())
        else:
            count += 1
    return count

def read_file(filename, zip_charset='cp866', use_unzip=False):
    # read the file
    if zipfile.is_zipfile(filename):
        zf = zipfile.ZipFile(filename)
        for z_filename in zf.namelist():
            # process each file
            try:
                uz_filename = unicode(z_filename, zip_charset)
            except UnicodeDecodeError, err:
                print_log('WARNING: decode zip filename:', str(err), level=1)
                uz_filename = filename
            if use_unzip:
                # sometimes, we have an error with zipfile module
                if os.name == 'nt':
                    unzip = os.path.join(os.path.dirname(sys.argv[0]),
                                         'unzip.exe')
                else:
                    unzip = 'unzip'
                uz_filename = z_filename
                if isinstance(filename, unicode):
                    enc = locale.getpreferredencoding()
                    filename = filename.encode(enc)
                if isinstance(z_filename, unicode):
                    enc = locale.getpreferredencoding()
                    z_filename = z_filename.encode(enc)
                cmd = subprocess.list2cmdline([unzip, '-p', filename,
                                               z_filename])
                p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                data, err = p.communicate()
                if err:
                    print_log('FATAL: unzip file:', err, level=3)
                    yield 'error', uz_filename, ''
                    continue
            else:
                try:
                    data = zf.read(z_filename)
                except:
                    yield 'error', uz_filename, ''
                    continue
            yield 'zip', uz_filename, data
    else:
        data = open(filename).read()
        yield 'plain', None, data

def walk(arg):
    if isinstance(arg, (str, unicode)):
        arg = [arg]
    for a in arg:
        if os.path.isdir(a):
            for root, dirs, files in os.walk(a):
                for filename in files:
                    filename = os.path.join(root, filename)
                    filename = os.path.normpath(filename)
                    if os.path.exists(filename):
                        yield filename
        else:
            filename = os.path.join(os.path.curdir, a)
            filename = os.path.normpath(filename)
            if os.path.exists(filename):
                yield filename

