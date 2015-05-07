"""Sharp and sparky static-site generator for periodic writers.
"""

from setuptools import setup


__author__ = 'Mahmoud Hashemi'
__version__ = '0.0.1'
__contact__ = 'mahmoud@hatnote.com'
__url__ = 'https://github.com/mahmoud/chert'
__license__ = 'BSD'


setup(name='chert',
      version=__version__,
      description="Sharp and sparky static-site generation.",
      long_description=__doc__,
      author=__author__,
      author_email=__contact__,
      url=__url__,
      packages=['chert'],
      include_package_data=True,
      zip_safe=False,
      license=__license__,
      platforms='any',
      entry_points={'console_scripts': ['chert = chert.core:main']},
      classifiers=[
          'Intended Audience :: Developers',
          'Topic :: Software Development :: Libraries',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.4', ]
      )
