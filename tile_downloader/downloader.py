import os
import math
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image
from tqdm import tqdm
import concurrent.futures
from typing import Tuple, List, Union, Optional

class TileDownloader:
    def __init__(self, tile_server_url_template: str, save_dir: str, num_workers: int = 10, convert_to_webp: bool = False):
        """Initialize downloader settings."""
        self.tile_server_url_template = tile_server_url_template
        self.save_dir = save_dir
        self.num_workers = num_workers
        self.convert_to_webp = convert_to_webp
        self.default_user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                   'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        self.default_timeout = 30
        self.max_retries_config = 5
        self.backoff_factor_config = 1.5
        self.error_csv_filename = 'download_errors.csv'
        self.inter_request_delay = None

    def lat_lon_to_tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert geographic coordinates to tile numbers at given zoom level."""
        n = 2.0 ** zoom
        x_tile = int((lon + 180.0) / 360.0 * n)
        y_tile = int((1.0 - (math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi)) / 2.0 * n)
        return x_tile, y_tile

    def create_session(self) -> requests.Session:
        """Create HTTP session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries_config,
            read=self.max_retries_config,
            connect=self.max_retries_config,
            backoff_factor=self.backoff_factor_config,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=self.num_workers, pool_maxsize=self.num_workers)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def download_tile(self, session: requests.Session, z: int, x: int, y: int) -> Optional[str]:
        """Download a single tile and save it to disk."""
        url = self.tile_server_url_template.format(x=x, y=y, z=z)
        tile_path_base = os.path.join(self.save_dir, str(z), str(x))
        filename = os.path.join(tile_path_base, f"{y}.png")
        os.makedirs(tile_path_base, exist_ok=True)
        headers = {'User-Agent': self.default_user_agent}

        try:
            response = session.get(url, headers=headers, timeout=self.default_timeout, stream=True)
            response.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if self.convert_to_webp:
                self.convert_to_webp_and_remove_original(filename)

            if self.inter_request_delay:
                time.sleep(self.inter_request_delay)

            return None
        except requests.RequestException as e:
            if os.path.exists(filename):
                os.remove(filename)
            return str(e)

    def convert_to_webp_and_remove_original(self, filepath: str):
        """Convert downloaded tile to optimized WEBP format and remove original PNG."""
        try:
            img = Image.open(filepath).convert('RGBA')
            webp_path = filepath.replace('.png', '.webp')
            img.save(webp_path, 'WEBP', quality=60, method=6)
            img.close()
            os.remove(filepath)
        except Exception as e:
            print(f"Error converting to WEBP: {e}")

    def download_tiles_from_bbox(self, bbox: Tuple[float, float, float, float], zoom_levels: Union[int, List[int]]):
        """Download all tiles within a bounding box at specified zoom levels."""
        if isinstance(zoom_levels, int):
            zoom_levels = [zoom_levels]

        session = self.create_session()
        errors = []

        for zoom in zoom_levels:
            x1, y1 = self.lat_lon_to_tile(bbox[2], bbox[1], zoom)
            x2, y2 = self.lat_lon_to_tile(bbox[0], bbox[3], zoom)

            tiles_to_download = [
                (zoom, x, y)
                for x in range(min(x1, x2), max(x1, x2) + 1)
                for y in range(min(y1, y2), max(y1, y2) + 1)
                if not os.path.exists(os.path.join(self.save_dir, str(zoom), str(x), f"{y}.png"))
            ]

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                futures = {executor.submit(self.download_tile, session, z, x, y): (z, x, y) for z, x, y in tiles_to_download}

                for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc=f"Downloading Zoom {zoom}"):

                    z, x, y = futures[future]
                    error = future.result()
                    if error:
                        errors.append({'zoom': z, 'x': x, 'y': y, 'error': error})

        if errors:
            self.save_errors_to_csv(errors)
