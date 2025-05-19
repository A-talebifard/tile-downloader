# Tile Downloader

A Python library for downloading map tiles from tile servers such as OpenStreetMap or other XYZ tile services. It supports multithreaded downloading, retry logic, bounding box-based selection, and optional WebP conversion.

## Features

- Convert bbox to tile coordinates
- Download tiles in parallel using threads
- Retry on network failures with exponential backoff
- Save tiles in organized folder structure
- Optional conversion to `.webp` format for optimized storage
- Logs failed downloads to CSV

## Installation

Install the package via pip:

```bash
pip install tile-downloader
```

## Usage

```python
from tile_downloader import TileDownloader

# Initialize downloader
downloader = TileDownloader(
    tile_server_url_template="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    save_dir="./tiles",
    num_workers=20,
    convert_to_webp=True
)

# Define bounding box (lat_min, lon_min, lat_max, lon_max)
bbox = (35.0, 51.0, 36.0, 52.0)

# Download tiles for zoom levels 12 to 14
downloader.download_tiles_from_bbox(bbox, zoom_levels=[12, 13, 14])
```

## Parameters

| Parameter               | Type            | Description |
|------------------------|-----------------|-------------|
| `tile_server_url_template` | `str` | URL template with `{z}`, `{x}`, `{y}` placeholders |
| `save_dir`             | `str`           | Directory to save downloaded tiles |
| `num_workers`          | `int`           | Number of threads (default: 10) |
| `convert_to_webp`      | `bool`          | Convert downloaded PNGs to WebP (default: False) |

## Output Structure

Tiles are saved in:

```
save_dir/
    {z}/
        {x}/
            {y}.png (or .webp)
```

Example: `tiles/12/2345/1546.png`

## Error Logging

Failed downloads are saved to a CSV file named `download_errors.csv` in the root directory with columns:

- zoom
- x
- y
- error

## License

This project is licensed under the MIT License © 2025 A.Talebifard – see the [LICENSE](LICENSE) file for details.


## Author

A.Talebifard – [abbastalebifard@gmail.com](mailto:abbastalebifard@gmail.com)

---

Feel free to contribute, report issues, or suggest improvements!
