from setuptools import setup, find_packages

setup(
    name='tile_downloader',
    version='0.15',
    packages=find_packages(),
    install_requires=[
        'requests',
        'Pillow',
        'tqdm',
    ],
    author='Abbas Talebifard',
    author_email='Abbastalebifard@gmail.com',
    description='A tile downloader utility',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/A-Talebifard/tile-downloader',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
