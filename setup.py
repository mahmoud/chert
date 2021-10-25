"""Sharp and sparky static-site generator for periodic writers.
"""

from setuptools import setup
from chert import __version__

__author__ = 'Mahmoud Hashemi'
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
      entry_points={'console_scripts': ['chert = chert.cli:main']},
      install_requires=['ashes>=19.2.0',
                        'boltons>=20.0.0',
                        'face>=20.1.1',
                        'lithoxyl>=21.0.0',
                        'Markdown>=3.1',
                        'python-dateutil>=2.8.0',
                        'PyYAML>=5.1.0',
                        'html5lib>=1.0.1',
                        'hyperlink>=18.0.0'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Topic :: Internet :: WWW/HTTP',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.9']
      )
