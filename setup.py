#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# (c) Lankier mailto:lankier@gmail.com
import os
from distutils.core import setup
from distutils.command.install_data import install_data
if os.name == 'nt':
    import py2exe

from fb2utils.utils import prog_version

class my_install_data(install_data):
    # for install data files to library dir
    def run(self):
        # need to change self.install_dir to the actual library dir
        install_cmd = self.get_finalized_command('install')
        self.install_dir = getattr(install_cmd, 'install_lib')
        return install_data.run(self)
kw = {
    'name': 'fb2utils',
    'version': prog_version,
    'url': 'http://code.google.com/p/fb2utils/',
    'author': 'Lankier',
    'author_email': 'lankier@gmail.com',
    'description': 'Utilities for manipulation fb2 files.',
    'license': 'GPL3',
    'scripts': ['fb2validator.py', 'fb2recovery.py',
                'fb2stat.py', 'validator-gui.py',
                'librusec-updater.py'],
    'packages': ['fb2utils', 'unidecode'],
    'cmdclass': {'install_data': my_install_data},
    'data_files': [['fb2utils/fb221schema',
                   ['fb2utils/fb221schema/FictionBook2.21.xsd',
                    'fb2utils/fb221schema/FictionBookGenres.xsd',
                    'fb2utils/fb221schema/FictionBookLang.xsd',
                    'fb2utils/fb221schema/FictionBookLinks.xsd',
                    ]]],
    }

if os.name == 'nt':
    kw['windows'] = [{'script': 'validator-gui.py'}]
    kw['console'] = ['fb2recovery.py',
                     'fb2stat.py',
                     'fb2validator.py',
                     'librusec-updater.py']
    del kw['cmdclass']
    kw['data_files'] = [['.',
                         ['fb2utils/fb221schema/FictionBook2.21.xsd',
                          'fb2utils/fb221schema/FictionBookGenres.xsd',
                          'fb2utils/fb221schema/FictionBookLang.xsd',
                          'fb2utils/fb221schema/FictionBookLinks.xsd',
                          ]]]

setup(**kw)
