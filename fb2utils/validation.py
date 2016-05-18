#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import sys
import os
import traceback
from cStringIO import StringIO
from xml.sax import handler, make_parser
from xml.sax.saxutils import escape
from lxml import etree
from optparse import OptionParser, make_option
import locale

from parser import FB2Parser
from utils import print_log, read_file, prog_version, LogOptions, check_xml, walk

##
## Validation
##

class SaxHandler(handler.ContentHandler):
    pass
parser = make_parser()
parser.setContentHandler(SaxHandler())
def sax_lint(data):
    s = StringIO(data)
    parser.parse(s)


schema_dir = 'fb221schema'
schema_file = 'FictionBook2.21.xsd'
def get_xsd_dir():
    xsd = None
    for d in sys.path:
        # search dir "fb221schema" in modules path
        for sd in (os.path.join(d, 'fb221schema'),
                   os.path.join(d, 'fb2utils', 'fb221schema')):
            if os.path.exists(sd):
                xsd = sd
                break
        if xsd:
            break
    assert xsd # xsd dir not found. check your installation
    return xsd

def get_xsd():
    if os.path.exists(schema_file):
        return os.path.abspath(schema_file)
    d = os.path.dirname(sys.argv[0])
    f = os.path.join(d, schema_file)
    if os.path.exists(f):
        return f
    return os.path.join(get_xsd_dir(), schema_file)

schema = None
def lxml_lint(data, type_='xml'):
    global schema
    def plog(msg, error_log):
        log = []
        for s in error_log:
            log.append('  Line %s: Column %s: %s' % (s.line, s.column, s.message))
        log = '\n'+'\n'.join(log)
        #print_log('Schemas validity ERROR:', str(schema.error_log))
        print_log(msg, log)

    parser = etree.XMLParser(ns_clean=True)
    try:
        xml = etree.fromstring(data, parser)
    except Exception, err:
        plog('DOM validity ERROR:', parser.error_log)
        return None
    if type_ == 'fb2':
        if schema is None:
            #schema = etree.XMLSchema(file=get_xsd()) # segfault
            curdir = os.path.abspath(os.path.curdir)
            xsd = get_xsd()
            os.chdir(os.path.dirname(xsd))
            schema = etree.XMLSchema(etree.XML(open(xsd).read()))
            os.chdir(curdir)
        r = schema.validate(xml)
        if not r:
            plog('Schemas validity ERROR:', schema.error_log)
            return None
    return xml

def validate(data, type='xml', log_msg='', quiet=False):
    if log_msg:
        log_msg = log_msg+':'
    # sax validation
    if type == 'sax':
        try:
            sax_lint(data)
        except Exception, err:
            #traceback.print_exc()
            print_log(log_msg, 'sax validity check failed')
            return None
        if not quiet:
            print_log(log_msg, 'sax validity check passed')
        return True
    # lxml (libxml2) validation
    try:
        xml = lxml_lint(data, type)
    except:
        traceback.print_exc()
        return None
    if xml is None:
        print_log(log_msg, type, 'validity check failed')
    else:
        if not quiet:
            print_log(log_msg, type, 'validity check passed')
    return xml

def check_tags(soup):
    errors = 0
    for t in soup.findAll(True):
        if t.name not in FB2Parser.NESTABLE_TAGS:
            print_log('FATAL: unknown tag:', t.name, level=3)
            return -1
        #print t.name, t.parent.name
        if t.parent.name not in FB2Parser.NESTABLE_TAGS[t.name]:
            print_log('WARNING: nestable tag: <%s> in <%s>'
                      % (t.name, t.parent.name), level=1)
            errors += 1
    return errors

def check_links(xml, quiet=False):
    errors = 0
    warnings = 0                        # not used yet
    href_list = []                      # list of (tag, type, href)
    hrefs = []                          # list of href
    ns = {'xlink':'http://www.w3.org/1999/xlink',
          'l':'http://www.w3.org/1999/xlink'}
    find = etree.XPath("//*[@xlink:href|@l:href]", namespaces=ns)
    for e in find(xml):
        type = e.attrib.get('type')
        txt = e.attrib['{http://www.w3.org/1999/xlink}href']
        href_list.append((e.tag, type, txt, e.sourceline))
        hrefs.append(txt)
    id_list = []                        # list of (tag, id)
    ids = []                            # list of id
    find = etree.XPath("//*[@id]", namespaces=ns)
    for e in find(xml):
        id_list.append((e.tag, e.attrib['id'], e.sourceline))
        ids.append(e.attrib['id'])
    for tag, type, href, line in href_list:
        if not href:
            print_log('ERROR: empty link')
            continue
        if not href.startswith('#'):
            if tag.endswith('}image'):
                print_log('ERROR: Line %s: external image: %s' % (line, href))
                errors += 1
                continue
            if type == 'note':
                print_log('ERROR: Line %s: external note: %s' % (line, href))
                errors += 1
                continue
            if not (href.startswith('http:') or
                    href.startswith('https:') or
                    href.startswith('ftp:') or
                    href.startswith('mailto:')):
                print_log('ERROR: Line %s: bad external link: %s' % (line, href))
                errors += 1
                #print_log('WARNING: local external link:', href)
                #warnings += 1
        elif href[1:] not in ids:
            print_log('ERROR: Line %s: bad internal link: %s' % (line, href))
            errors += 1
    for tag, id, line in id_list:
        if tag.endswith('}binary') and '#'+id not in hrefs:
            print_log('ERROR: Line %s: not linked image: %s' % (line, id))
            errors += 1
    return errors

def check_empty_tags(xml):
    errs = 0
    find = etree.XPath('//*')
    for e in find(xml):
        if (not e.getchildren() and
            not e.tag.endswith('empty-line') and
            not e.tag.endswith('image') and
            not e.tag.endswith('sequence')):
            if e.text is None or not e.text.strip():
                print_log('WARNING: Line %s: empty tag: %s' %
                          (e.sourceline, e.tag), level=1)
                errs += 1
    return errs

##
## Functions for command-line util
##

class html_markup:
    h2 = ('<h2>', '</h2>')
    h3 = ('<h3>', '</h3>')
    h4 = ('<h4>', '</h4>')
    good = ('<h3 style="color: green">', '</h3>')
    bad = ('<h3 style="color: red">', '</h3>')
    err = ('', '')
    hr = '<hr />'
class txt_markup:
    h2 = ('***', '***')
    h3 = ('**', '**')
    h4 = ('*', '*')
    good = ('>', '<')
    bad = ('>', '<')
    err = ('', '')
    hr = '-'*72
markup = txt_markup

def print_markup(s=None, m=None):
    if s is None:
        if isinstance(LogOptions.outfile, list):
            LogOptions.outfile.append(m)
        else:
            print >> LogOptions.outfile, m
        return
    if isinstance(s, (tuple, list)):
        s = ' '.join(s)
    if isinstance(s, unicode):
        enc = locale.getpreferredencoding()
        s = s.encode(enc)
    begin, end = m
    if options.html:
        s = escape(s)
    if isinstance(LogOptions.outfile, list):
        LogOptions.outfile.append((s, m))
    else:
        print >> LogOptions.outfile, begin, s, end
    

def check_file(data):
    if not check_xml(data):
        return False
    print_markup('Try the DOM parser', markup.h4)
    xml = validate(data, 'xml', quiet=options.quiet)
    if xml is None:
        return False
    out = []
    if not options.quiet:
        out += LogOptions.outfile
    LogOptions.outfile = []             # clear output
    print_markup('Schema validation', markup.h4)
    fb2 = validate(data, 'fb2', quiet=options.quiet)
    ret = 0
    if fb2 is None:
        ret = 1
        out += LogOptions.outfile
        #return False
    elif not options.quiet:
        out += LogOptions.outfile
    LogOptions.outfile = []             # clear output
    print_markup('Extra FB2 checkup', markup.h4)
    err = check_links(xml, quiet=options.quiet)
    err += check_empty_tags(xml)
    if err or not options.quiet:
        out += LogOptions.outfile
    ret += err
    LogOptions.outfile = out
    if ret != 0:
        return False
    return True

def do_process_file(filename):
    errors = 0
    output = [('Validation of file '+filename, markup.h2)]
    for file_format, z_filename, data in read_file(filename):
        LogOptions.outfile = []
        out = []
        err = 0
        if z_filename is not None:
            out.append(('Zipped file found: '+z_filename, markup.h3))
        if file_format == 'error':
            out.append(('FATAL: read file error', markup.bad))
            err += 1
        else:
            c = check_file(data)
            out += LogOptions.outfile
            if c:
                out.append(('OK. This file is good', markup.good))
            else:
                errors += 1
                err += 1
                if not options.quiet:
                    out.append(('Some errors found', markup.bad))
        if err or not options.quiet:
            output += out
            output.append(markup.hr)
    return errors, output


def process_file(filename):
    # process one file
    outfile = LogOptions.outfile
    errors, output = do_process_file(filename)
    if errors or not options.quiet:
        for s in output:
            if isinstance(s, tuple):
                print >> outfile, s[1][0], s[0], s[1][1]
            else:
                print >> outfile, s
    LogOptions.outfile = outfile
    return errors

options = None
def main():
    # parsing command-line options
    global options, markup
    option_list = [
        make_option("-o", "--out", dest="outfile",
                    help="write result to FILE", metavar="FILE"),
        make_option("-m", "--html", dest="html", action="store_true",
                    default=False, help="output in HTML"),
        make_option("-q", "--quiet", dest="quiet", action="store_true",
                    default=False, help="show errors only"),
        ]
    parser = OptionParser(option_list=option_list,
                          usage="usage: %prog [options] files|dirs",
                          version="%prog "+prog_version)
    options, args = parser.parse_args()
    LogOptions.level = 0                # show all errors
    if options.html:
        markup = html_markup
        LogOptions.br = '<br />'
        LogOptions.escape = True
    if options.outfile:
        LogOptions.outfile = open(options.outfile, 'at')
    else:
        LogOptions.outfile = sys.stdout
    errors = 0
    for f in walk(args):
        errors += process_file(f)
    sys.exit(errors)

