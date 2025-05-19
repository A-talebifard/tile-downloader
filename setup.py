from setuptools import setup, find_packages

setup(
    name='tile_downloader',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'requests',
        'Pillow',
        'tqdm',
    ],
    author='Abbas Talebifard',
    author_email='Abbastalbeifard@gmail.com',
    description='A tile downloader utility',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/tile_downloader',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
