# Tile Downloader

A Python library and GUI application for downloading map tiles from XYZ tile servers such as OpenStreetMap, Google Maps, or Esri. Supports multithreaded downloading, robust retry logic, bounding box or GeoJSON-based tile selection, optional WebP conversion, and export to **PMTiles** format.

## Features

- Download tiles by bounding box (lat/lon) **or GeoJSON geometry**
- Parallel downloading using thread pools
- Configurable retry logic with exponential backoff
- Save tiles in organized XYZ folder structure (`z/x/y.png`)
- Optional conversion to `.webp` for smaller file sizes
- Export downloaded tiles to a single **PMTiles** file
- Built-in **Graphical User Interface (GUI)** for easy use
- Logs failed downloads to `download_errors.csv`

## Installation

Install the package via pip:

```bash
pip install tile-downloader
```

To launch the GUI:

```bash
tile-downloader-gui
```

## Usage (Programmatic)

```python
from tile_downloader import TileDownloader

# Initialize downloader
downloader = TileDownloader(
    tile_server_url_template="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    save_dir="./tiles",
    num_workers=20,
    convert_to_webp=True
)

# Option 1: Download by bounding box (lat_min, lon_min, lat_max, lon_max)
bbox = (35.0, 51.0, 36.0, 52.0)
downloader.download_tiles_from_bbox(bbox, zoom_levels=[12, 13, 14])

# Option 2: Download from GeoJSON (file path or dict)
downloader.download_tiles_from_geojson("area.geojson", zoom_levels=[12, 13, 14])

# Option 3: Export to PMTiles after download
downloader.download_tiles_from_bbox(
    bbox,
    zoom_levels=[12],
    create_pmtiles=True,
    pmtiles_filename="output.pmtiles",
    delete_source_after_pmtiles=False
)
```

## Parameters

| Parameter                  | Type            | Description |
|---------------------------|-----------------|-------------|
| `tile_server_url_template`| `str`           | URL template with `{z}`, `{x}`, `{y}` placeholders |
| `save_dir`                | `str`           | Directory to save downloaded tiles |
| `num_workers`             | `int`           | Number of concurrent threads (default: 10) |
| `convert_to_webp`         | `bool`          | Convert downloaded PNGs to WebP (default: False) |
| `create_pmtiles`          | `bool`          | Export tiles to a single `.pmtiles` file |
| `pmtiles_filename`        | `str`           | Output filename when `create_pmtiles=True` |
| `delete_source_after_pmtiles` | `bool`      | Remove XYZ tiles after PMTiles export |

## Output Structure

Tiles are saved in:

```
save_dir/
    {z}/
        {x}/
            {y}.png (or .webp)
```

Example: `tiles/12/2345/1546.png`

When PMTiles export is enabled, a single `output.pmtiles` file is generated containing all downloaded tiles.

## Error Logging

Failed downloads are saved to `download_errors.csv` in the save directory with columns:

- `zoom`
- `x`
- `y`
- `error`

## Demo

See the GUI in action:

![Tile Downloader](demo.gif)

## License

This project is licensed under the MIT License © 2025 A.Talebifard – see the [LICENSE](LICENSE) file for details.

## Author

A.Talebifard – [abbastalebifard@gmail.com](mailto:abbastalebifard@gmail.com)

---
Feel free to contribute, report issues, or suggest improvements!
