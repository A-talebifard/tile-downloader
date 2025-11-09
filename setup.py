from setuptools import setup, find_packages

# Read the contents of your README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='tile_downloader',
    version='1.0.0',  # Bumped to a final version
    packages=find_packages(),
    install_requires=[
        'requests',
        'Pillow',
        'tqdm',
        'shapely',
        'pyproj',
        'pmtiles',
    ],
    python_requires='>=3.7',
    author='Abbas Talebifard',
    author_email='Abbastalebifard@gmail.com',
    description='A utility for downloading map tiles from various providers based on geographic boundaries.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/A-Talebifard/tile-downloader',
    license='MIT',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: GIS',
        'Topic :: Utilities',
    ],

    entry_points={
        'console_scripts': [
            'tile-downloader-gui = tile_downloader_gui.TileDownloaderGUI:main',
        ],
    },
)