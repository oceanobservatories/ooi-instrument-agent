from setuptools import setup

setup(
    name='OOI Instrument Agent',
    version='0.0.4',
    long_description=__doc__,
    packages=['ooi_instrument_agent'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['Flask>=0.10',
                      'gevent>=1.1',
                      'pyzmq>=15.0',
                      'python-consul>=0.6',
                      'twisted']
)
