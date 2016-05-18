#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import sys
import os
import time
from optparse import OptionParser, make_option
import zipfile
import traceback
from lxml import etree

from parser import FB2Parser
from validation import validate, check_tags
from edition import add_desc, norm_desc
from utils import prog_version, read_file, walk, print_log, LogOptions, check_xml

##
## Processing
##

def parse(data):
    # return values:
    # 0 - good file
    # 1 - fixed
    # -1 - not fixed

    # pre validation
##     if options.pre_fb2lint:
##         if validate(data, 'fb2', 'PRE') is not None:
##             return 0
##     else:
    if not options.force and validate(data, 'xml', 'PRE') is not None:
        return 0

    # parsing and recovery
    try:
        soup = FB2Parser(data, convertEntities='xml')
    except:
        traceback.print_exc()
        print_log('FATAL: exception', level=3)
        return -1
    ret = 1

    # post validation #1
    xml = validate(str(soup.FictionBook), 'xml', 'POST')
    if xml is None:
        print_log('FATAL: not fixed', level=3)
        return -1

    # post processing
    ##add_desc(soup)
    ##norm_desc(soup)

    # post validation #2
    #check_tags(soup)
##     if options.post_fb2lint:
##         if validate(data, 'fb2', 'POST') is None:
##             ret = -1

    if options.check_only:
        return ret

    data = etree.tostring(xml, encoding=options.output_encoding,
                          xml_declaration=True)

    # save result
    def add_suffix(fn):
        root, ext = os.path.splitext(fn)
        return root+'-fixed'+ext
    newfilename = None
    zipfilename = None
    z = False                           # zip result ?
    # filenames
    if not options.nozip:
        if options.z_filename or options.zip:
            z = True
    newfilename = add_suffix(options.filename)
    if z:
        if not newfilename.endswith('.zip'):
            newfilename = add_suffix(newfilename+'.zip')
        newfilename = add_suffix(newfilename)
        if options.z_filename:
            zipfilename = options.z_filename
        else:
            zipfilename = options.filename
        zipfilename = os.path.basename(zipfilename)
    else:
        if options.z_filename:
            d = os.path.dirname(options.filename)
            newfilename = add_suffix(os.path.join(d, options.z_filename))
    if options.outfile:
        newfilename = options.outfile
    if options.dest_dir:
        f = os.path.basename(newfilename)
        newfilename = os.path.join(options.dest_dir, f)

    if os.path.exists(newfilename):
        print_log('FATAL: could not save file, file exists:',
                  newfilename, level=3)
        return
    if newfilename == '-':
        z = False
    # save
    if options.verbose:
        print_log('save:', newfilename)
    if z:
        zf = zipfile.ZipFile(newfilename, 'w')
        zf.writestr(zipfilename, data)
    else:
        if newfilename == '-':
            sys.stdout.write(data)
        else:
            open(newfilename, 'w').write(data)


total_files = 0
def process_file(filename):
    global total_files
    options.filename = os.path.abspath(filename)
    LogOptions.filename = os.path.abspath(filename)
    for file_format, z_filename, data in read_file(filename):
        options.file_format = file_format
        options.z_filename = z_filename
        LogOptions.z_filename = z_filename
        total_files += 1
        if file_format == 'error':
            print_log('FATAL: read file error', level=3)
            continue
        if not check_xml(data):
            continue
        # run parsing
        parse(data)

##
## Main
##

options = None
def main():
    # parsing command-line options
    global options
    option_list = [
        make_option("-o", "--out", dest="outfile",
                    help="write result to FILE", metavar="FILE"),
        make_option("-d", "--dest-dir", dest="dest_dir",
                    help="save result files to DIR", metavar="DIR"),
        make_option("-z", "--zip", dest="zip", action="store_true",
                    default=False, help="zip result file"),
        make_option("-n", "--no-zip", dest="nozip", action="store_true",
                    default=False, help="don't zip result file"),
        make_option("-c", "--check-only", dest="check_only",
                    action="store_true", default=False,
                    help="check only, do not save result"),
        make_option("-f", "--force", dest="force", action="store_true",
                    default=False, help="don't validate XML"),
##         make_option("-b", "--pre-fb2-lint", dest="pre_fb2lint",
##                     action="store_true", default=False,
##                     help="pre process FB2 validation"),
##         make_option("-a", "--post-fb2-lint", dest="post_fb2lint",
##                     action="store_true", default=False,
##                     help="post process FB2 validation"),
        make_option("-e", "--output-encoding", dest="output_encoding",
                    default = 'utf-8', metavar="ENC",
                    help="fb2 output encoding"),
        make_option("-v", "--verbose", dest="verbose", action="store_true",
                    default=False, help="more info"),
        make_option("-q", "--quiet", dest="quiet", action="store_true",
                    default=False, help="less info"),
        ]
    parser = OptionParser(option_list=option_list,
                          usage="usage: %prog [options] files|dirs",
                          version="%prog "+prog_version)
    options, args = parser.parse_args()

    if options.verbose:
        LogOptions.level = 0
    elif options.quiet:
        LogOptions.level = 2

    starttime = time.time()
    # walk a files
    for filename in walk(args):
        process_file(filename)
    # print stats
    if options.verbose:
        et = time.time() - starttime
        print 'elapsed time: %.2f secs' % et
        print 'average: %.3f secs' % (et/total_files)



##
if __name__ == '__main__':
    main()
