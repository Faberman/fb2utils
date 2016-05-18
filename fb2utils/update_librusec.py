#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import sys, os
import time
import shutil
import sqlite3
from cStringIO import StringIO
from lxml import etree
from copy import deepcopy
from optparse import OptionParser, make_option
import zipfile
import traceback

from utils import walk, read_file, prog_version, print_log, LogOptions, check_xml, count_files, print_exc
from parser import FB2Parser

# global vars
db_file = None
_connect = None
options = None
not_deleted_list = None
update_time = None
fsenc = sys.getfilesystemencoding()
namespaces = {'m': 'http://www.gribuser.ru/xml/fictionbook/2.0',
              'xlink':'http://www.w3.org/1999/xlink',
              'l':'http://www.w3.org/1999/xlink'}
# statistics
class stats:
    total_files = 0
    total = 0
    passed = 0
    fixed = 0
    errors = 0

def insert_values(curs, tbl_name, s):
    i = s.index('VALUES') + len('VALUES')
    values = s[i:].strip()
    if values.endswith(';'):
        values = values[:-1]
    values = values.split('),(')
    for v in values:
        if not v.startswith('('):
            v = '(' + v
        if not v.endswith(')'):
            v = v + ')'
        v = v.replace('\\\\', '\x00')   # temporary replace backslashes
        v = v.replace("\\'", "''")      # replace escape \' -> ''
        v = v.replace('\x00', '\\')     # return backslashes
        sql = 'insert into %s values %s' % (tbl_name, v)
        try:
            curs.execute(sql)
        except:
            print 'SQL:', repr(sql)
            raise

def mksql(fn, tbl_name):
    global _connect
    curs = _connect.cursor()
    curs.execute('DROP TABLE IF EXISTS `%s`' % tbl_name)
    sql = []
    start = False
    data = open(fn).read(2)
    if data == '\x1f\x8b':
        import gzip
        f = gzip.open(fn, 'rb')
        data = f.read()
        f.close()
        fd = StringIO(data)
    else:
        fd = open(fn)
    for s in fd:
        if s.startswith(')'):
            break
        if s.startswith('CREATE TABLE'):
            start = True
            sql.append('CREATE TABLE `%s` (\n' % tbl_name)
        elif start:
            if s.strip().startswith('KEY'):
                continue
            elif s.strip().startswith('FULLTEXT KEY'):
                continue
            elif s.strip().startswith('UNIQUE KEY'):
                continue
            else:
                #s = s.replace('auto_increment', 'AUTOINCREMENT')
                s = s.replace('auto_increment', '')
                s = s.replace('character set utf8', '')
                s = s.replace('collate utf8_bin', '')
                s = s.replace('collate utf8_unicode_ci', '')
                s = s.replace('unsigned', '')
                s = s.replace('COMMENT', ', --')
                s = s.replace('USING BTREE', '')
                #s = s.replace('UNIQUE KEY', 'UNIQUE')
                sql.append(s)
    sql = ''.join(sql).strip()
    if sql.endswith(','):
        sql = sql[:-1]
    sql = sql+'\n)'
    curs.execute(sql)
    #
    update_time = None
    found = False
    for s in fd:
        if s.startswith('INSERT INTO'):
            insert_values(curs, tbl_name, s)
            found = True
        elif s.startswith('-- Dump completed on'):
            ut = s[len('-- Dump completed on'):].strip().replace('  ', ' ')
            if update_time is None:
                update_time = ut
            else:
                update_time = min(ut, update_time)
    _connect.commit()
    if not found:
        raise ValueError('insert sql instruction not found')
    return update_time

def update_db():
    global _connect
    sql_tables = (
        #('lib.libactions.sql', 'libactions'),
        #('lib.libavtoraliase.sql', 'libavtoraliase'),
        ('lib.libavtorname.sql', 'libavtorname'),
        ('lib.libavtor.sql', 'libavtor'),
        #('lib.libblocked.sql', 'libblocked'),
        ('lib.libbook.old.sql', 'libbookold'),
        ('lib.libbook.sql', 'libbook'),
        #('lib.libdonations.sql', 'libdonations'),
        #('lib.libfilename.sql', 'libfilename'),
        ('lib.libgenrelist.sql', 'libgenrelist'),
        ('lib.libgenre.sql', 'libgenre'),
        #('lib.libjoinedbooks.sql', 'libjoinedbooks'),
        #('lib.libpolka.sql', 'libpolka'),
        ('lib.libseqname.sql', 'libseqname'),
        ('lib.libseq.sql', 'libseq'),
        #('lib.libsrclang.sql', 'libsrclang'),
        ('lib.libtranslator.sql', 'libtranslator'),
        )
    update_time = None
    for fn, tbl_name in sql_tables:
        fn = os.path.join(options.sql_dir, fn)
        if not os.path.exists(fn):
            fn = fn + '.gz'
            if not os.path.exists(fn):
                print_log('ERROR: file not found:', fn, level=3)
                return False
        ut = mksql(fn, tbl_name)
        if tbl_name != 'libbookold':
            # skip libbookold
            update_time = ut
    curs = _connect.cursor()
    curs.execute('DROP TABLE IF EXISTS librusec')
    curs.execute('CREATE TABLE librusec ( update_time varchar(32) )')
    curs.execute('INSERT INTO librusec VALUES (?)', (update_time,))
    _connect.commit()
    return True

# ????????????:
#   T - translit
#   L - lowercase
#   R - remove FAT invalid chars
#   B - big file names (do not strip file names to 255 chars)
#   _ - replace all space to underscore
# ??????????:
#   m - meta genre
#   g - genre
#   L - first letter in author last-name
#   f - authors full-name
#   F - first author full-name
#   a - authors last-name (or nickname)
#   A - first author last-name (or nickname)
#   t - title
#   s - (sequence #numder)
#   S - sequence number
def get_filename(book_info):
    format = options.fn_format
    f = format.split(':')
    mods = ''
    if len(f) > 2:
        return None
    if len(f) == 2:
        mods, format = f
    if '_' in mods:
        sep = '_'
    else:
        sep = ' '
    fn_tbl = {
        'm': 'metagen',
        'g': 'genre',
        'l': 'lang',
        't': 'title',
        'L': 'first_letter',
        'a': 'name',
        'A': 'first_name',
        'f': 'full_name',
        'F': 'first_full_name',
        's': 'seq1',
        'S': 'seq2',
        'b': 'bookid',
        }
    #
    book_info['bookid'] = str(book_info['bookid'])
    # metagenre
    book_info['metagen'] = list(book_info['metagen'])[0]
    # genre
    book_info['genre'] = book_info['genres'][0]
    # authors
    full_names = []
    names = []
    first_name = ''
    first_full_name = ''
    first_letter = ''
    for a in book_info['authors']:
        aut = []
        name = a[2]
        if a[2]:                        # last-name
            aut.append(a[2])
            aut.append(a[0])
            aut.append(a[1])
        elif a[3]:                      # nickname
            aut.append(a[3])
            name = a[3]
        else:
            aut.append(a[2])
            aut.append(a[0])
            aut.append(a[1])
        aut = sep.join(aut).strip()
        full_names.append(aut)
        names.append(name)
        if not first_name:
            first_name = name
            first_full_name = aut
            first_letter = aut[0]
    if len(names) > 3:
        # ???????
        names = [names[0], '...']
        full_names = [full_names[0], '...']
    if '_' in mods:
        book_info['name'] = '_'.join(names)
        book_info['full_name'] = '_'.join(full_names)
    else:
        book_info['name'] = ', '.join(names)
        book_info['full_name'] = ', '.join(full_names)
    book_info['first_name'] = first_name
    book_info['first_full_name'] = first_full_name
    book_info['first_letter'] = first_letter.upper()
    # sequence
    if book_info['sequences']:
        seq = tuple(book_info['sequences'][0])
        book_info['seq1'] = '(%s #%s)' % seq
        book_info['seq2'] = '%s %s' % seq
    else:
        book_info['seq1'] = book_info['seq2'] = ''
    # replace '/' and '\'
    for n in ('name', 'full_name', 'first_name', 'first_full_name',
              'title', 'seq1', 'seq2'):
        book_info[n] = book_info[n].replace('/', '%').replace('\\', '%')
    # generate filename
    f = []
    for c in list(format):
        if c in fn_tbl:
            k = book_info[fn_tbl[c]]
            if k:
                f.append(k)
            elif c in 'sS':
                if f and f[-1] == ' ':
                    f = f[:-1]
        else:
            f.append(c)
    fn = ''.join(f)
    #
    fn = fn.strip()
    if 'R' in mods:
        for c in '|?*<>":+[]':          # invalid chars in VFAT
            fn = fn.replace(c, '')
    if '_' in mods:
        fn = fn.replace(' ', '_')
    if 'L' in mods:
        fn = fn.lower()
    if 'T' in mods:
        # translit
        from unidecode import unidecode
        fn = unidecode(fn)
    elif not os.path.supports_unicode_filenames:
        fn = fn.encode(fsenc, 'replace')
    max_path_len = 247
    if 'B' not in mods and len(fn) > max_path_len:
        fn = fn[:max_path_len]
        if fsenc.lower() == 'utf-8':
            # utf-8 normalisation
            fn = unicode(fn, 'utf-8', 'ignore').encode('utf-8')
    fn = os.path.join(options.out_dir, fn)
    return fn

def get_bookid(filename, fb2):
    global _connect
    # search bookid in fb2
    if options.search_id and fb2 is not None:
        find = xpath('/m:FictionBook/m:description/m:custom-info')
        bookid = None
        for e in find(fb2):
            bid = e.get('librusec-book-id')
            if bid is not None:
                try:
                    bookid = int(bid)
                except:
                    pass
                else:
                    return bookid
    # search bookid by filename
    try:
        bookid = int(filename)
    except ValueError:
        curs = _connect.cursor()
        curs.execute("SELECT BookId FROM libbookold WHERE FileName = ?",
                     (filename,))
        res = curs.fetchone()
        if res is None:
            print_log('ERROR: file not found in db:', filename, level=3)
            return None
        return res[0]
    return bookid

def is_deleted(bookid):
    global _connect
    curs = _connect.cursor()
    curs.execute("SELECT Deleted FROM libbook WHERE BookId = ?", (bookid,))
    res = curs.fetchone()
    if res is None:
        print >> sys.stderr, 'updatedb.is_deleted: internal error'
        return None
    return bool(res[0])

def create_fb2(data):
    if not check_xml(data):
        return None
    try:
        fb2 = etree.XML(data)
    except:
        #print_exc()
        if not options.nofix:
            try:
                data = str(FB2Parser(data, convertEntities='xml'))
                options.file_fixed = True
                fb2 = etree.XML(data)
            except:
                print_exc()
                return None
            else:
                stats.fixed += 1
        else:
            return None
    return fb2

_xpath_cash = {}
def xpath(path):
    # optimisation
    if path in _xpath_cash:
        return _xpath_cash[path]
    find = etree.XPath(path, namespaces=namespaces)
    _xpath_cash[path] = find
    return find

def update_fb2(fb2, bookid):
    # initialisation
    # 1. db
    global _connect
    curs = _connect.cursor()
    # 2. xml
    find = xpath('/m:FictionBook/m:description/m:title-info')
    old_ti = find(fb2)[0]               # old <title-info>
    new_ti = etree.Element('title-info') # new <title-info>
    # 3. routines
    xp_prefix = '/m:FictionBook/m:description/m:title-info/m:'
    def copy_elem(elem):
        # just copy old elements
        find = xpath(xp_prefix+elem)
        for e in find(fb2):
            new_ti.append(deepcopy(e))
    def add_authors(table, column, elem_name, add_unknown=False):
        authors = []
        sql = '''SELECT
        FirstName, MiddleName, LastName, NickName, Homepage, Email
        FROM libavtorname JOIN %s ON libavtorname.AvtorId = %s.%s
        WHERE BookId = ?''' % (table, table, column)
        curs.execute(sql, (bookid,))
        res = curs.fetchall()
        if res:
            for a in res:
                author = etree.Element(elem_name)
                aut = []
                i = 0
                for e in ('first-name', 'middle-name', 'last-name',
                          'nickname', 'home-page', 'email'):
                    if a[i]:
                        elem = etree.Element(e)
                        elem.text = a[i]
                        author.append(elem)
                        aut.append(a[i])
                    else:
                        aut.append('')
                    i += 1
                new_ti.append(author)
                authors.append(aut)
        elif add_unknown:
            author = etree.Element(elem_name)
            elem = etree.Element('last-name')
            elem.text = u'????? ??????????'
            author.append(elem)
            new_ti.append(author)
            authors.append(['', '', u'????? ??????????', ''])
        return authors
    #
    book_info = {'bookid': bookid}
    # generation <title-info>
    # 1. <genre>
    curs.execute('SELECT GenreId FROM libgenre WHERE BookId = ?', (bookid,))
    genres = []
    metagen = set()
    res = curs.fetchall()
    if res:
        for i in res:
            curs.execute('''SELECT GenreCode, GenreMeta FROM libgenrelist
            WHERE GenreId = ? LIMIT 1''', i)
            res = curs.fetchone()
            name = res[0]
            genre = etree.Element('genre')
            genre.text = name
            new_ti.append(genre)
            genres.append(name)
            metagen.add(res[1])
    else:
        genres = ['other']
        genre = etree.Element('genre')
        genre.text = 'other'
        new_ti.append(genre)
        metagen = [u'??????']
    book_info['genres'] = genres
    book_info['metagen'] = metagen
    # 2. <author>
    authors = add_authors('libavtor', 'AvtorId', 'author', add_unknown=True)
    book_info['authors'] = authors
    # 3. <book-title>
    curs.execute('''SELECT Title, Title1, Lang, Time FROM libbook
    WHERE BookId = ? LIMIT 1''', (bookid,))
    title_text, title1_text, lang_text, added_time = curs.fetchone()
    lang_text = lang_text.lower()
    title_text = title_text.strip()
    title1_text = title1_text.strip()
    title = etree.Element('book-title')
    if title1_text:
        title.text = '%s [%s]' % (title_text, title1_text)
    else:
        title.text = title_text
    new_ti.append(title)
    book_info['title'] = title_text
    book_info['title1'] = title1_text
    # 4. <annotation>
    copy_elem('annotation')
    # 5. <keywords>
    copy_elem('keywords')
    # 6. <date>
    copy_elem('date')
    # 7. <coverpage>
    copy_elem('coverpage')
    # 8. <lang>
    lang = etree.Element('lang')
    lang.text = lang_text
    new_ti.append(lang)
    book_info['lang'] = lang_text
    # 9. <src-lang>
    copy_elem('src-lang')
    # 10. <translator>
    add_authors('libtranslator', 'TranslatorId', 'translator')
    # 11. <sequence>
    sequences = []
    if 1:
        curs.execute("""SELECT SeqName, SeqNumb
        FROM libseq JOIN libseqname USING (SeqId)
        WHERE BookId = ? AND SeqName != '' """, (bookid,))
    else:
        curs.execute("""SELECT SeqName, SeqNumb
        FROM libseq JOIN libseqname USING(SeqId)
        WHERE BookId = ? ORDER BY level LIMIT 1""", (bookid,))
    for seq in curs.fetchall():
        sequence = etree.Element('sequence')
        sequence.attrib['name'] = seq[0]
        sequence.attrib['number'] = str(seq[1])
        new_ti.append(sequence)
        sequences.append([seq[0], str(seq[1])])
    book_info['sequences'] = sequences
    # finalisation
    # 1. replace <title-info>
    find = xpath('/m:FictionBook/m:description')
    desc = find(fb2)[0]
    desc.replace(old_ti, new_ti)
    # 2. add/update <custom-info>
    bookid_found = False
    add_ti_found = False
    added_time_found = False
    update_time_found = False
    updater_found = False
    fixer_found = False
    find = xpath('/m:FictionBook/m:description/m:custom-info')
    for ci in find(fb2):
        it = ci.get('info-type')
        if not it:
            if it is None:
                print_log('WARNING: <custom-info> has no attribute "info-type"')
        elif it == 'librusec-book-id':
            bookid_found = True
        elif it == 'librusec-add-title-info':
            ci.text = title1_text
            add_ti_found = True
        elif it == 'librusec-added-at':
            ci.text = added_time
            added_time_found = True
        elif it == 'librusec-updated-at':
            ci.text = update_time
            update_time_found = True
        elif it == 'librusec-updater' and ci.text == 'fb2utils':
            updater_found = True
        elif it == 'fixed-by' and ci.text == 'fb2utils':
            fixer_found = True
    if not bookid_found:
        ci = etree.Element('custom-info')
        ci.attrib['info-type'] = 'librusec-book-id'
        ci.text = str(bookid)
        desc.append(ci)
    if not add_ti_found and title1_text:
        ci = etree.Element('custom-info')
        ci.attrib['info-type'] = 'librusec-add-title-info'
        ci.text = title1_text
        desc.append(ci)
    if not added_time_found:
        ci = etree.Element('custom-info')
        ci.attrib['info-type'] = 'librusec-added-at'
        ci.text = added_time
        desc.append(ci)
    if not update_time_found:
        ci = etree.Element('custom-info')
        ci.attrib['info-type'] = 'librusec-updated-at'
        ci.text = update_time
        desc.append(ci)
    if not updater_found:
        ci = etree.Element('custom-info')
        ci.attrib['info-type'] = 'librusec-updater'
        ci.text = 'fb2utils'
        desc.append(ci)
    if options.file_fixed and not fixer_found:
        ci = etree.Element('custom-info')
        ci.attrib['info-type'] = 'fixed-by'
        ci.text = 'fb2utils'
        desc.append(ci)
    # done
    return etree.tostring(fb2, encoding=options.output_encoding,
                          xml_declaration=True), book_info

def copy_fb2(filename, data, to_dir=None, msg='save bad fb2 file:'):
    if to_dir is None:
        if not options.save_bad:
            return
        to_dir = options.save_bad
    filename = str(filename)+'.fb2'
    fn = os.path.join(to_dir, filename)
    print_log(msg, fn)
    if options.nozip:
        open(fn).write(data)
    else:
        save_zip(fn, filename, data)

def save_zip(out_file, out_fn, data):
    out_file = out_file+'.zip'
    zf = zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED)
    zipinfo = zipfile.ZipInfo()
    zipinfo.filename = out_fn
    zipinfo.external_attr = 0644 << 16L # needed since Python 2.5
    zipinfo.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(zipinfo, data)
    #zf.writestr(out_fn, data)

def base_name(filename, ext='.fb2'):
    if not filename.endswith(ext):
        return None
    return os.path.basename(filename)[:-len(ext)]

def process_file(fn, ftype, z_filename, data):
    # 0. logging
    LogOptions.filename = os.path.abspath(fn)
    stats.total += 1
    options.file_fixed = False
    if options.log_file and (stats.total % 10) == 0:
        # progress
        tm = time.time() - stats.starttime
        eta = stats.total_files * tm / stats.total - tm
        h = int(eta / 3600)
        m = (eta - h * 3600) / 60
        s = eta % 60
        sys.stdout.write('\r%d out of %d (ETA: %02dh %02dm %02ds)' %
                         (stats.total, stats.total_files, h, m, s))
        sys.stdout.flush()
    if ftype == 'error':
        # unzip error
        print_log('ERROR:', z_filename, level=3)
        stats.errors += 1
        return False
    filename = fn
    if z_filename:
        LogOptions.z_filename = z_filename
        filename = z_filename
    # 1. search bookid
    f = base_name(filename)
    if f is None:
        # filename does not ends with 'fb2'
        stats.errors += 1
        print_log('ERROR: bad filename:', z_filename, level=3)
        copy_fb2('unknown-id-'+str(stats.errors), data)
        return False
    if options.search_id:
        fb2 = create_fb2(data)
        bookid = get_bookid(f, fb2)
    else:
        bookid = get_bookid(f, None)
    if bookid is None:
        stats.errors += 1
        print_log('ERROR: unknown bookid', level=3)
        copy_fb2('unknown-id-'+str(stats.errors), data)
        return False
    print_log('bookid =', str(bookid))
    # 2. check is deleted
    if not options.nodel and bookid not in not_deleted_list:
        print_log('deleted, skip')
        if options.save_deleted:
            copy_fb2(bookid, data, options.save_deleted,
                     'save deleted file:')
        return False
    # 3. update not_deleted_list
    if bookid in not_deleted_list:
        not_deleted_list.remove(bookid)
    else:
        print 'INTERNAL ERROR:', bookid, 'not in not_deleted_list'
    # 4. create fb2 (dom) if not
    if not options.search_id:
        fb2 = create_fb2(data)
    if fb2 is None:
        stats.errors += 1
        copy_fb2(bookid, data)
        return False
    # 5. update
    if not options.noup:
        try:
            d, book_info = update_fb2(fb2, bookid)
        except:
            print_exc()
            stats.errors += 1
            copy_fb2(bookid, data)
            return False
        data = d
    # 6. save result
    out_fn = str(bookid)+'.fb2'
    if options.fn_format:
        out_file = get_filename(book_info)
        if not out_file:
            out_file = os.path.join(options.out_dir, out_fn)
        else:
            out_file = out_file+'.fb2'
            d = os.path.dirname(out_file)
            if os.path.isdir(d):
                pass
            elif os.path.exists(d):
                print_log('ERROR: file exists:', d, level=3)
                return False
            else:
                os.makedirs(d)
    else:
        out_file = os.path.join(options.out_dir, out_fn)
    if options.nozip:
        open(out_file, 'w').write(data)
    else:
        try:
            save_zip(out_file, out_fn, data)
        except:
            print
            print '>>', len(out_file), out_file
            raise
    stats.passed += 1
    return True

def process(arg):
    global not_deleted_list, update_time
    curs = _connect.cursor()
    res = curs.execute("SELECT BookId FROM libbook WHERE NOT (Deleted&1) and FileType = 'fb2' ")
    not_deleted_list = curs.fetchall()
    not_deleted_list = set([i[0] for i in not_deleted_list])
    curs.execute('SELECT * FROM librusec')
    update_time = curs.fetchone()[0]
    for fn in walk(arg):
        for ftype, z_filename, data in read_file(fn, zip_charset='utf-8'):
            process_file(fn, ftype, z_filename, data)
    if options.search_deleted:
        deleted = set()
        for fn in walk(options.search_deleted):
            bookid = base_name(fn, '.fb2.zip')
            try:
                bookid = int(bookid)
            except ValueError:
                continue
            if bookid in not_deleted_list:
                deleted.append(fn)
        for fn in deleted:
            for ftype, z_filename, data in read_file(fn, zip_charset='utf-8'):
                ret = process_file(fn, ftype, z_filename, data)
                if ret:
                    print_log('restore deleted:', bookid)
    print
    print 'processed:', stats.total
    print 'passed:', stats.passed
    print 'fixed:', stats.fixed
    print 'errors:', stats.errors
    if options.not_found:
        fd = open(options.not_found, 'w')
        for bookid in not_deleted_list:
            print >> fd, bookid

def main():
    # parsing command-line options
    global options, db_file, _connect
    sql_dir = os.path.join(os.path.dirname(sys.argv[0]), 'sql')
    option_list = [
        make_option("-o", "--out-dir", dest="out_dir",
                    metavar="DIR", help="save updated fb2 files to this dir"),
        make_option("-g", "--generate-db", dest="update_db",
                    action="store_true", default=False,
                    help="generate db"),
        make_option("-d", "--do-not-delete", dest="nodel",
                    action="store_true", default=False,
                    help="don't delete duplicate files"),
        make_option("-f", "--do-not-fix", dest="nofix",
                    action="store_true", default=False,
                    help="don't fix an xml"),
        make_option("-u", "--do-not-update", dest="noup",
                    action="store_true", default=False,
                    help="don't update fb2 meta info"),
        make_option("-z", "--do-not-zip", dest="nozip",
                    action="store_true",
                    default=False, help="don't zip result files"),
        make_option("-i", "--search-id", dest="search_id",
                    action="store_true",
                    default=False, help="search bookid in fb2"),
        make_option("-a", "--save-deleted", dest="save_deleted",
                    metavar="DIR", help="save deleted fb2 files to this dir"),
        make_option("-c", "--search-deleted", dest="search_deleted",
                    metavar="DIR", help="search deleted fb2 files in this dir"),
        make_option("-b", "--save-bad-fb2", dest="save_bad",
                    metavar="DIR", help="save bad fb2 files to this dir"),
        make_option("-s", "--sql-dir", dest="sql_dir",
                    default=sql_dir, metavar="DIR",
                    help="search sql files in this dir"),
        make_option("-e", "--output-encoding", dest="output_encoding",
                    default = 'utf-8', metavar="ENC",
                    help="fb2 output encoding"),
        make_option("-l", "--log-file", dest="log_file",
                    metavar="FILE",
                    help="output log to this file"),
        make_option("-n", "--not-found-file", dest="not_found",
                    metavar="FILE",
                    help="save missing books to this file"),
        make_option("-F", "--filename-pattern", dest="fn_format",
                    metavar="PATTERN",
                    help="output filenames pattern"),
        ]
    parser = OptionParser(option_list=option_list,
                          usage=("usage: %prog [options] "
                                 "input-files-or-dirs"),
                          version="%prog "+prog_version)
    options, args = parser.parse_args()
    LogOptions.level = 0
    db_file = os.path.join(options.sql_dir, 'db.sqlite')
    _connect = sqlite3.connect(db_file)
    if options.update_db:
        # update db
        print_log('start update db')
        ret = update_db()
        if ret:
            print_log('done')
        else:
            print_log('fail')
            return
        if len(args) == 0:
            return
    #
    if len(args) == 0:
        sys.exit('wrong num args')
    in_file = args[0]
    if not options.out_dir:
        sys.exit('option --out-dir required')
    for f in args:
        if not os.path.exists(f):
            sys.exit('file does not exists: '+f)
    if not os.path.isdir(options.out_dir):
        sys.exit('dir does not exists: '+options.out_dir)
    if options.save_bad and not os.path.isdir(options.save_bad):
        sys.exit('dir does not exists: '+options.save_bad)
    if options.save_deleted and not os.path.isdir(options.save_deleted):
        sys.exit('dir does not exists: '+options.save_deleted)
    if not os.path.exists(db_file):
        print_log('start update db')
        ret = update_db()
        if ret:
            print_log('done')
        else:
            print_log('fail')
            return
    #
    stats.total_files = count_files(args)
    print 'total files:', stats.total_files
    if options.log_file:
        LogOptions.outfile = open(options.log_file, 'w')
    stats.starttime = time.time()
    process(args)
    et = time.time() - stats.starttime
    print 'elapsed time: %.2f secs' % et


if __name__ == '__main__':
    #main()
    print update_fb2(open('../example.fb2').read(), 55142)

