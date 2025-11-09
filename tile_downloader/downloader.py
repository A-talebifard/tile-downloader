import os
import math
import shutil
import time
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image
import concurrent.futures
import threading
from typing import Tuple, List, Union, Optional, Callable
import csv
import json

from shapely.geometry import shape, box
import pyproj
from pmtiles.tile import zxy_to_tileid, TileType, Compression
from pmtiles.writer import Writer


class StoppableThreadPoolExecutor(concurrent.futures.ThreadPoolExecutor):
    """A ThreadPoolExecutor that can be stopped gracefully by checking a threading.Event."""

    def __init__(self, max_workers=None, stop_event=None, *args, **kwargs):
        super().__init__(max_workers, *args, **kwargs)
        self._stop_event = stop_event or threading.Event()

    def submit(self, fn, *args, **kwargs):
        if self._stop_event.is_set():
            future = concurrent.futures.Future()
            future.set_exception(concurrent.futures.CancelledError())
            return future
        return super().submit(fn, *args, **kwargs)


class TileDownloader:
    """Handles all backend logic: GIS processing, downloading, and PMTiles conversion."""

    def __init__(self, tile_server_url_template: str, save_dir: str, num_workers: int = 10,
                 convert_to_webp: bool = False):
        self.tile_server_url_template = tile_server_url_template
        self.save_dir = save_dir
        self.num_workers = num_workers
        self.convert_to_webp = convert_to_webp
        self.default_user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        self.default_timeout = 30
        self.max_retries_config = 5
        self.backoff_factor_config = 1.5
        self.error_csv_filename = 'download_errors.csv'
        self.inter_request_delay = None
        self.tile_cache_dir = os.path.join(self.save_dir, "tiles")  # Dedicated directory for XYZ tiles

    def _get_srid_from_geojson(self, geojson_data: dict) -> int:
        """Attempts to detect the SRID from a GeoJSON 'crs' member."""
        try:
            crs_urn = geojson_data['crs']['properties']['name']
            match = re.search(r'EPSG::(\d+)', crs_urn)
            if match:
                srid = int(match.group(1))
                print(f"Detected source SRID from GeoJSON: {srid}")
                return srid
        except (KeyError, TypeError):
            pass
        print("No specific SRID found in GeoJSON, assuming default WGS84 (4326).")
        return 4326

    def _convert_to_pmtiles(self, output_file: str, delete_source: bool,
                            progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """Converts the downloaded XYZ tiles to a single PMTiles file."""
        tiles_to_process = []
        detected_tile_type = TileType.UNKNOWN
        min_zoom, max_zoom = float('inf'), -1
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), -1, -1
        phase_name = "Converting to PMTiles"

        if progress_callback:
            progress_callback(0, 1, phase_name)

        for root, _, files in os.walk(self.tile_cache_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ('.png', '.jpg', '.jpeg', '.webp'):
                    if detected_tile_type == TileType.UNKNOWN:
                        if ext == '.png':
                            detected_tile_type = TileType.PNG
                        elif ext in ('.jpg', '.jpeg'):
                            detected_tile_type = TileType.JPG
                        elif ext == '.webp':
                            detected_tile_type = TileType.WEBP
                    try:
                        path_parts = os.path.normpath(root).split(os.sep)
                        z = int(path_parts[-2])
                        x = int(path_parts[-1])
                        y = int(os.path.splitext(file)[0])
                        tiles_to_process.append((z, x, y, os.path.join(root, file)))
                        min_zoom, max_zoom = min(min_zoom, z), max(max_zoom, z)
                        min_x, min_y = min(min_x, x), min(min_y, y)
                        max_x, max_y = max(max_x, x), max(max_y, y)
                    except (ValueError, IndexError):
                        continue

        if not tiles_to_process:
            raise FileNotFoundError("No tiles found in the source directory to convert.")

        # Calculate accurate bounding box
        nw_lon, nw_lat = self.tile_to_lat_lon(min_x, min_y, max_zoom)
        se_lon, se_lat = self.tile_to_lat_lon(max_x + 1, max_y + 1, max_zoom)
        bounds = (nw_lon, se_lat, se_lon, nw_lat)

        total_tiles = len(tiles_to_process)
        with open(output_file, "wb") as f:
            writer = Writer(f)
            processed_count = 0
            for z, x, y, tile_path in sorted(tiles_to_process, key=lambda t: (t[0], t[1], t[2])):
                tileid = zxy_to_tileid(z, x, y)
                with open(tile_path, "rb") as tile_file:
                    tile_data = tile_file.read()
                writer.write_tile(tileid, tile_data)
                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, total_tiles, phase_name)

            writer.finalize({
                "tile_type": detected_tile_type,
                "tile_compression": Compression.GZIP,  # <--- ADDED THIS LINE
                "min_zoom": min_zoom, "max_zoom": max_zoom,
                "min_lon_e7": int(bounds[0] * 10 ** 7), "min_lat_e7": int(bounds[1] * 10 ** 7),
                "max_lon_e7": int(bounds[2] * 10 ** 7), "max_lat_e7": int(bounds[3] * 10 ** 7),
                "center_zoom": max_zoom,
                "center_lon_e7": int(((bounds[0] + bounds[2]) / 2) * 10 ** 7),
                "center_lat_e7": int(((bounds[1] + bounds[3]) / 2) * 10 ** 7),
            }, {"attribution": "Created with Tile Downloader"})

        if delete_source:
            shutil.rmtree(self.tile_cache_dir)

    def download_tiles_from_geojson(self, geojson_input: Union[str, dict], zoom_levels: Union[int, List[int]],
                                    progress_callback: Optional[Callable[[int, int, str], None]] = None,
                                    stop_event: Optional[threading.Event] = None, create_pmtiles: bool = False,
                                    pmtiles_filename: str = "output.pmtiles",
                                    delete_source_after_pmtiles: bool = False):
        if isinstance(geojson_input, str):
            with open(geojson_input, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
        elif isinstance(geojson_input, dict):
            geojson_data = geojson_input
        else:
            raise TypeError("geojson_input must be a file path or a dictionary.")

        source_srid = self._get_srid_from_geojson(geojson_data)
        stop_event = stop_event or threading.Event()
        download_phase_name = "Downloading"
        if isinstance(zoom_levels, int): zoom_levels = [zoom_levels]
        bboxes = self._calculate_bboxes_from_geojson(geojson_data, source_srid)
        if not bboxes: raise ValueError("No valid geometries found in GeoJSON.")

        all_tiles_to_download = set()
        for bbox in bboxes:
            for zoom in zoom_levels:
                x1, y1 = self.lat_lon_to_tile(bbox[3], bbox[0], zoom)  # lat_max, lon_min
                x2, y2 = self.lat_lon_to_tile(bbox[1], bbox[2], zoom)  # lat_min, lon_max
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    for y in range(min(y1, y2), max(y1, y2) + 1):
                        tile_dir = os.path.join(self.tile_cache_dir, str(zoom), str(x))
                        png_path = os.path.join(tile_dir, f"{y}.png")
                        webp_path = os.path.join(tile_dir, f"{y}.webp")
                        if not os.path.exists(png_path) and not os.path.exists(webp_path):
                            all_tiles_to_download.add((zoom, x, y))

        total_tiles = len(all_tiles_to_download)
        if progress_callback: progress_callback(0, total_tiles, download_phase_name)

        if total_tiles > 0:
            session = self.create_session()
            errors = []
            completed_tiles = 0
            with StoppableThreadPoolExecutor(max_workers=self.num_workers, stop_event=stop_event) as executor:
                futures = {executor.submit(self.download_tile, session, z, x, y): (z, x, y) for z, x, y in
                           all_tiles_to_download}
                try:
                    for future in concurrent.futures.as_completed(futures):
                        if stop_event.is_set():
                            for f in futures: f.cancel()
                            break
                        try:
                            error = future.result()
                            if error:
                                z, x, y = futures[future]
                                errors.append({'zoom': z, 'x': x, 'y': y, 'error': error})
                        except concurrent.futures.CancelledError:
                            pass
                        completed_tiles += 1
                        if progress_callback: progress_callback(completed_tiles, total_tiles, download_phase_name)
                finally:
                    executor.shutdown(wait=True, cancel_futures=True)
            if errors: self.save_errors_to_csv(errors)

        if create_pmtiles and not stop_event.is_set():
            output_path = os.path.join(self.save_dir, pmtiles_filename)
            self._convert_to_pmtiles(output_path, delete_source_after_pmtiles, progress_callback)

    def download_tiles_from_bbox(self, bbox: Tuple[float, float, float, float], zoom_levels: Union[int, List[int]],
                                 **kwargs):
        min_lat, min_lon, max_lat, max_lon = bbox
        geom = box(min_lon, min_lat, max_lon, max_lat)
        mock_geojson = {
            "type": "Feature",
            "geometry": geom.__geo_interface__
        }
        self.download_tiles_from_geojson(geojson_input=mock_geojson, zoom_levels=zoom_levels, **kwargs)

    def _calculate_bboxes_from_geojson(self, geojson_data: dict, source_srid: int) -> List[
        Tuple[float, float, float, float]]:
        geometries = []
        if geojson_data.get('type') == 'FeatureCollection':
            features = geojson_data.get('features', [])
            for feature in features:
                if feature.get('geometry'): geometries.append(shape(feature['geometry']))
        elif geojson_data.get('geometry'):
            geometries.append(shape(geojson_data['geometry']))
        elif geojson_data.get('type'):
            geometries.append(shape(geojson_data))
        else:
            raise ValueError("Invalid GeoJSON structure.")

        transformer = None
        if source_srid != 4326:
            source_crs = pyproj.CRS(f"EPSG:{source_srid}")
            target_crs = pyproj.CRS("EPSG:4326")
            transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

        bboxes = []
        for geom in geometries:
            if not geom.is_valid: geom = geom.buffer(0)
            single_geoms = list(geom.geoms) if hasattr(geom, 'geoms') else [geom]
            for part in single_geoms:
                if transformer:
                    bounds = transformer.transform_bounds(*part.bounds)
                else:
                    bounds = part.bounds
                # bounds are (min_lon, min_lat, max_lon, max_lat)
                bboxes.append(bounds)
        return bboxes

    def lat_lon_to_tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        n = 2.0 ** zoom
        x_tile = int((lon + 180.0) / 360.0 * n)
        lat_rad = math.radians(lat)
        y_tile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return x_tile, y_tile

    def tile_to_lat_lon(self, x: int, y: int, zoom: int) -> Tuple[float, float]:
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return lon_deg, lat_deg

    def create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(total=self.max_retries_config, read=self.max_retries_config,
                               connect=self.max_retries_config, backoff_factor=self.backoff_factor_config,
                               status_forcelist=(429, 500, 502, 503, 504), allowed_methods=["HEAD", "GET", "OPTIONS"])
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=self.num_workers,
                              pool_maxsize=self.num_workers)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def download_tile(self, session: requests.Session, z: int, x: int, y: int) -> Optional[str]:
        url = self.tile_server_url_template.format(x=x, y=y, z=z)
        tile_path_base = os.path.join(self.tile_cache_dir, str(z), str(x))
        os.makedirs(tile_path_base, exist_ok=True)

        original_filename = os.path.join(tile_path_base, f"{y}.png")
        final_filename = os.path.join(tile_path_base, f"{y}.webp") if self.convert_to_webp else original_filename

        headers = {'User-Agent': self.default_user_agent}
        try:
            response = session.get(url, headers=headers, timeout=self.default_timeout, stream=True)
            response.raise_for_status()
            with open(original_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if self.convert_to_webp:
                self.convert_image_to_webp(original_filename, final_filename)

            if self.inter_request_delay: time.sleep(self.inter_request_delay)
            return None
        except requests.RequestException as e:
            if os.path.exists(original_filename): os.remove(original_filename)
            return str(e)
        except Exception as e:
            if os.path.exists(original_filename): os.remove(original_filename)
            return f"Error during processing: {e}"

    def convert_image_to_webp(self, source_path: str, dest_path: str):
        """Converts an image to WEBP format and removes the original."""
        try:
            with Image.open(source_path) as img:
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(dest_path, 'webp')
            os.remove(source_path)
        except Exception as e:
            if source_path != dest_path and os.path.exists(source_path):
                os.rename(source_path, dest_path.replace('.webp', '.png'))
            raise IOError(f"Failed to convert {source_path} to WEBP: {e}")

    def save_errors_to_csv(self, errors: List[dict]):
        if not errors: return
        error_file_path = os.path.join(self.save_dir, self.error_csv_filename)
        fieldnames = list(errors[0].keys())
        try:
            with open(error_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(errors)
            print(f"\nSaved {len(errors)} download errors to: {error_file_path}")
        except IOError as e:
            print(f"\nCould not write errors to file {error_file_path}: {e}")

