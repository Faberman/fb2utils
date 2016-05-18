#!/usr/bin/env python
# -*- mode: python; coding: utf-8; -*-
# (c) Lankier mailto:lankier@gmail.com

try:
    import psyco
    psyco.full()
except ImportError:
    print 'oops! psyco is not installed...'
    pass
from fb2utils.update_librusec import main
#import cProfile
#cProfile.run('main()', 'prof.db')
main()
