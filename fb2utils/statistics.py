#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import sys
import os
import time

from validation import validate, check_tags, check_links
from utils import print_log, read_file, walk, LogOptions, check_xml

##
## Statistics
##

class Stat:
    total = 0                           # total files
    good = 0
    not_xml = 0
    sax_errors = 0
    xml_errors = 0                      # bad xml
    fb2_errors = 0                      # bad fb2
    extra_errors = 0                    # bad links, images, etc
    links_errors = 0
    images_errors = 0
    fixed = 0
    passed = 0
    starttime = 0

def calc_statistics(data):
    good = True
    xml = validate(data, 'fb2')         # fb2 schema
    if xml is None:
        good = False
        bad_fb2 = True
        xml = validate(data, 'xml')     # dom parser
        if xml is None:
            if validate(data, 'sax') is None: # sax parser
                Stat.sax_errors += 1
            else:
                Stat.xml_errors += 1
            return
        else:
            Stat.fb2_errors += 1
    if check_links(xml) != 0:           # links
        good = False
        Stat.extra_errors += 1
        Stat.links_errors += 1
    if good:
        Stat.good += 1


def process_file(filename):
    # process one file
    LogOptions.filename = os.path.abspath(filename)
    for file_format, z_filename, data in read_file(filename):
        LogOptions.z_filename = z_filename
        Stat.total += 1
        if file_format == 'error':
            Stat.not_xml += 1
            print_log('FATAL: read file error', level=3)
            continue
        if not check_xml(data):
            Stat.not_xml += 1
            continue
        calc_statistics(data)


def main():
    LogOptions.level = 0
    Stat.starttime = time.time()
    for f in walk(sys.argv[1:]):
        process_file(f)
    # print stats
    def p_stat(msg, v):
        print '%s: %d (%d%%)' % (msg, v, round(v*100./Stat.total))
    print 'total files:', Stat.total
    p_stat('not an xml file', Stat.not_xml)
    p_stat('sax parsing error', Stat.sax_errors)
    p_stat('dom parsing error', Stat.xml_errors)
    p_stat('fb2 schema violation', Stat.fb2_errors)
    p_stat('inconsistent fb2 file', Stat.extra_errors)
    p_stat('good files', Stat.good)
    et = time.time() - Stat.starttime
    print 'elapsed time: %.2f secs' % et
    print 'average: %.3f secs' % (et/Stat.total)


if __name__ == '__main__':
    main()
