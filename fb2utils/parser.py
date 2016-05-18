#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import re
import BeautifulSoup
import sgmllib

from utils import print_log

##
## Customizing SGML/HTML parser
##
class StartTagOpen:
    tag = re.compile('<[a-z][-a-z]*')
    def match(self, rawdata, i):
        if rawdata.startswith("<FictionBook", i):
            return True
        m = self.tag.match(rawdata, i)
        if not m:
            return False
        return m.group()[1:] in FB2Parser.NESTABLE_TAGS
sgmllib.starttagopen = StartTagOpen()
sgmllib.tagfind = re.compile('[a-zA-Z][-a-zA-Z]*')
if 1:
    # xml attribute, should be: key="value" or key = 'value'
    sgmllib.attrfind = re.compile(
        r'\s*([a-z][-:.a-z0-9]*)'       # key
        r'(\s*=\s*('                    # =
        r'\'[^\']*\'|"[^"]*"))'         # "value"
        )

##
## Main FB2 parser
##

class FB2Parser(BeautifulSoup.BeautifulStoneSoup):

    NESTABLE_TAGS = {
        'FictionBook': ['[document]'],
        'a': ['subtitle', 'text-author', 'p', 'v'],
        'annotation': ['title-info', 'src-title-info', 'section'],
        'author': ['title-info', 'src-title-info', 'document-info'],
        'binary': ['FictionBook'],
        'body': ['FictionBook'],
        'book-name': ['publish-info'],
        'book-title': ['title-info', 'src-title-info'],
        'cite': ['epigraph', 'annotation', 'section', 'history'],
        'city': ['publish-info'],
        'code': ['subtitle', 'text-author', 'p', 'v'],
        'coverpage': ['title-info', 'src-title-info'],
        'custom-info': ['description'],
        'date': ['title-info', 'src-title-info', 'document-info'],
        'description': ['FictionBook'],
        'document-info': ['description'],
        'email': ['author', 'translator'],
        'emphasis': ['subtitle', 'text-author', 'p', 'v'],
        'empty-line': ['section', 'annotation', 'epigraph', 'title', 'cite', 'history'],
        'epigraph': ['body', 'title', 'poem', 'section'],
        'first-name': ['author', 'translator'],
        'genre': ['title-info', 'src-title-info'],
        'history': ['document-info'],
        'home-page': ['author', 'translator'],
        'id': ['author', 'translator', 'document-info'],
        'image': ['body', 'subtitle', 'text-author', 'p', 'v', 'a', 'coverpage', 'section'],
        'isbn': ['publish-info'],
        'keywords': ['title-info', 'src-title-info'],
        'lang': ['title-info', 'src-title-info'],
        'last-name': ['author', 'translator'],
        'middle-name': ['author', 'translator'],
        'nickname': ['author', 'translator'],
        'p': ['annotation', 'title', 'section', 'cite', 'epigraph', 'history'],
        'poem': ['annotation', 'title', 'section', 'cite', 'epigraph', 'history'],
        'program-used': ['document-info'],
        'publish-info': ['description'],
        'publisher': ['publish-info'],
        'section': ['body', 'section'],
        'sequence': ['title-info', 'src-title-info', 'publish-info'],
        'src-lang': ['title-info', 'src-title-info'],
        'src-ocr': ['document-info'],
        'src-title-info': ['description'],
        'src-url': ['document-info'],
        'stanza': ['poem'],
        'strikethrough': ['subtitle', 'text-author', 'p', 'v'],
        'strong': ['subtitle', 'text-author', 'p', 'v'],
        'style': ['subtitle', 'text-author', 'p', 'v'],
        'stylesheet': ['FictionBook'],
        'sub': ['subtitle', 'text-author', 'p', 'v', 'a'],
        'subtitle': ['annotation', 'title', 'section', 'cite', 'epigraph', 'stanza', 'history'],
        'sup': ['subtitle', 'text-author', 'p', 'v', 'a'],
        'table': ['cite', 'annotation', 'section', 'history'],
        'td': ['table'],
        'text-author': ['cite', 'epigraph', 'poem', 'annotation'],
        'th': ['table'],
        'title': ['body', 'section', 'poem'],
        'title-info': ['description'],
        'tr': ['table'],
        'translator': ['title-info', 'src-title-info'],
        'v': ['stanza'],
        'version': ['document-info'],
        'year': ['publish-info'],
        }

    SELF_CLOSING_TAGS = BeautifulSoup.buildTagMap(
        None,
        ['image', 'empty-line', 'sequence'])

    # removed invalid xml chars
    rmchars = re.compile(u'[\x00-\x08\x0b\x0c\x0e-\x1f]+', re.U)

    def parse_starttag(self, i):
        j = self.rawdata.find('>', i)
        if j > 0:
            tag = self.rawdata[i:j].strip()
            if tag.endswith('/'):     # self closing tag (i.e. <empty-line />)
                tag = tag[:-1].strip()
            if ' ' in tag and '=' not in tag:
                # bad attribute
                self.handle_data(self.rawdata[i:j+1])
                return j+1
        return sgmllib.SGMLParser.parse_starttag(self, i)

    def unknown_starttag(self, name, attrs, selfClosing=0):
        #print 'unknown_starttag:', repr(name)
        if name == 'fictionbook':
            # sgmllib workaround
            name = 'FictionBook'
        if name not in self.NESTABLE_TAGS:
            # unknown tag
            print_log('unknown start tag:', name, level=2)
            #attrs = ''.join(map(lambda(x, y): ' %s="%s"' % (x, y), attrs))
            attrs = ' '.join(y for x, y in attrs)
            self.handle_data('<%s %s>' % (name, attrs))
            return
        BeautifulSoup.BeautifulStoneSoup.unknown_starttag(self, name, attrs,
                                                          selfClosing)

    def unknown_endtag(self, name):
        if name == 'fictionbook':
            # sgmllib workaround
            name = 'FictionBook'
        if name not in self.NESTABLE_TAGS:
            # unknown tag
            print_log('unknown end tag:', name, level=2)
            self.handle_data('</%s>' % name)
            return
        BeautifulSoup.BeautifulStoneSoup.unknown_endtag(self, name)

    def finish_starttag(self, tag, attrs):
        if attrs:
            if 'l:href' in (a[0] for a in attrs):
                # fix l:href namespace
                try:
                    self.FictionBook['xmlns:l']
                except KeyError:
                    self.FictionBook['xmlns:l'] = 'http://www.w3.org/1999/xlink'
            if 'xlink:href' in (a[0] for a in attrs):
                # fix xlink:href namespace
                try:
                    self.FictionBook['xmlns:xlink']
                except KeyError:
                    self.FictionBook['xmlns:xlink'] = 'http://www.w3.org/1999/xlink'
        if tag not in self.NESTABLE_TAGS:
            self.unknown_starttag(tag, attrs)
            return -1
        return sgmllib.SGMLParser.finish_starttag(self, tag, attrs)

    def finish_endtag(self, tag):
        if tag not in self.NESTABLE_TAGS:
            self.unknown_endtag(tag)
            return
        sgmllib.SGMLParser.finish_endtag(self, tag)

    def endData(self, containerClass=BeautifulSoup.NavigableString):
        #print 'endData', self.currentData
        if self.currentData:
            d = []
            for s in self.currentData:
                s = (s
                     .replace('&', '&amp;')
                     .replace('<', '&lt;')
                     .replace('>', '&gt;')
                     )
                s = self.rmchars.sub('', s)
                d.append(s)
            self.currentData = d
        BeautifulSoup.BeautifulStoneSoup.endData(self, containerClass)

    def parse_pi(self, i):
        # skip "<?"
        rawdata = self.rawdata
        if rawdata[i:i+5] != '<?xml':
            self.handle_data(rawdata[i:i+2])
            return 2
        return sgmllib.SGMLParser.parse_pi(self, i)

