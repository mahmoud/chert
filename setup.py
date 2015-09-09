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
      entry_points={'console_scripts': ['chert = chert.core:main']},
      install_requires=['hematite==0.0.2',
                        'ashes>=0.7.4',
                        'boltons==15.0.2',
                        'Markdown==2.6.2',
                        'Pygments==1.6',
                        'python-dateutil==2.2',
                        'PyYAML==3.11',
                        'lithoxyl',
                        'html5lib==0.999999'],
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Topic :: Internet :: WWW/HTTP',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.7']
      )
