#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

import traceback
import BeautifulSoup

from utils import prog_name, prog_version
_program_name = '%s v.%s' % (prog_name, prog_version)

##
## Change an FB2 file
##

def add_if_not_exists(soup, parent, tags):
    for tagname in tags:
        tag = parent.find(tagname, recursive=False)
        if not tag:
            tag = BeautifulSoup.Tag(soup, tagname)
            parent.insert(0, tag)
        parent = tag

def add_desc(soup, incr_version=0.01):
    # /description/document-info/program-used
    # /description/document-info/version
    add_if_not_exists(soup, soup.FictionBook.description,
                      ['document-info', 'version'])
    add_if_not_exists(soup, soup.FictionBook.description,
                      ['document-info', 'program-used'])
    di = soup.FictionBook.description.find('document-info', recursive=False)
    # increase version
    version = di.version
    text = version.string
    if text:
        try:
            text = float(text)
        except:
            traceback.print_exc()
        else:
            text += incr_version
            text = '%.2f' % text
            version.string.replaceWith(BeautifulSoup.NavigableString(text))
    else:
        version.insert(0, BeautifulSoup.NavigableString('0.01'))
    # add program-used
    program_used = di.find('program-used', recursive=False)
    text = program_used.string
    if text:
        text = '%s, %s' % (text, _program_name)
        program_used.string.replaceWith(BeautifulSoup.NavigableString(text))
    else:
        program_used.insert(0, BeautifulSoup.NavigableString(_program_name))
    #print soup.FictionBook.description.find('document-info', recursive=False)

def norm_desc(soup):
    titleInfoType = ('genre',
                     'author',
                     'book-title',
                     'annotation',
                     'keywords',
                     'date',
                     'coverpage',
                     'lang',
                     'src-lang',
                     'translator',
                     'sequence',)
    authorType = ('first-name',
                  'middle-name',
                  'last-name',
                  'nickname',
                  'home-page',
                  'email',)
    d = (
        ('description', ('title-info',
                         'src-title-info',
                         'document-info',
                         'publish-info',
                         'custom-info',)),
        ('title-info', titleInfoType),
        ('src-title-info', titleInfoType),
        ('document-info', ('author',
                           'program-used',
                           'date',
                           'src-url',
                           'src-ocr',
                           'id',
                           'version',
                           'history',)),
        ('publish-info', ('book-name',
                          'publisher',
                          'city',
                          'year',
                          'isbn',
                          'sequence',)),
        ('author', authorType),
        ('translator', authorType),
        )
    for parentname, tags in d:
        parentlist = soup.findAll(parentname)
        if not parentlist:
            continue
        for parent in parentlist:
            tag = BeautifulSoup.Tag(soup, parentname)
            for tagname in tags:
                for child in parent.findAll(tagname):
                    tag.insert(999999, child.extract())
            parent.replaceWith(tag)

