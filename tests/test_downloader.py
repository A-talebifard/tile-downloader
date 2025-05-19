import unittest
from tile_downloader import TileDownloader

class TestTileDownloader(unittest.TestCase):
    def test_lat_lon_to_tile(self):
        downloader = TileDownloader(
            tile_server_url_template='https://example.com/{x}/{y}/{z}.png',
            save_dir='./tiles'
        )
        lat, lon, zoom = 37.7749, -122.4194, 12
        x, y = downloader.lat_lon_to_tile(lat, lon, zoom)
        self.assertEqual(x, 1554)
        self.assertEqual(y, 1711)

if __name__ == '__main__':
    unittest.main()
