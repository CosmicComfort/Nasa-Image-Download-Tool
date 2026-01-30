"""
NASA Media Downloader - Android (Kivy) Application

This is the main entry point for the Android APK.
"""

import os
import sys
import threading
from pathlib import Path
from functools import partial

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label

# Import shared modules
try:
    from nasa_downloader.api.client import NasaAPI
    from nasa_downloader.api.session import make_session
    from nasa_downloader.api.quality import find_quality_urls
    from nasa_downloader.downloader.tasks import download_file
    from nasa_downloader.downloader.metadata import save_metadata
    from nasa_downloader.core.config import VIDEO_EXTENSIONS
except ImportError:
    # Fallback for development without full package
    NasaAPI = None


class SearchScreen(Screen):
    """Main search screen."""

    search_query = StringProperty('')
    status_text = StringProperty('Enter a search term to find NASA media')
    is_searching = BooleanProperty(False)


class ResultsScreen(Screen):
    """Search results screen."""

    results = ListProperty([])
    current_page = NumericProperty(1)
    has_more = BooleanProperty(False)


class DownloadScreen(Screen):
    """Download progress screen."""

    current_file = StringProperty('')
    progress = NumericProperty(0)
    total_files = NumericProperty(0)
    completed_files = NumericProperty(0)
    download_status = StringProperty('Preparing download...')


class SettingsScreen(Screen):
    """Settings screen."""

    download_images = BooleanProperty(True)
    download_videos = BooleanProperty(True)
    download_metadata = BooleanProperty(True)
    selected_quality = StringProperty('orig')
    max_items = NumericProperty(50)


class NasaDownloaderApp(App):
    """Main Kivy application."""

    title = 'NASA Media Downloader'

    # App state
    api = None
    session = None
    search_results = ListProperty([])
    download_queue = ListProperty([])
    is_downloading = BooleanProperty(False)

    # Settings
    download_path = StringProperty('')

    def build(self):
        """Build the application UI."""
        # Set download path
        if hasattr(self, 'user_data_dir'):
            self.download_path = os.path.join(self.user_data_dir, 'NASA-Downloads')
        else:
            self.download_path = os.path.join(os.path.expanduser('~'), 'NASA-Downloads')

        # Initialize API
        try:
            self.session = make_session()
            self.api = NasaAPI(session=self.session)
        except Exception as e:
            print(f"Failed to initialize API: {e}")

        # Create screen manager
        self.sm = ScreenManager()
        self.sm.add_widget(SearchScreen(name='search'))
        self.sm.add_widget(ResultsScreen(name='results'))
        self.sm.add_widget(DownloadScreen(name='download'))
        self.sm.add_widget(SettingsScreen(name='settings'))

        return self.sm

    def search(self, query: str, media_type: str = 'image'):
        """Perform a search."""
        if not self.api:
            self.show_error("API not initialized")
            return

        if not query.strip():
            self.show_error("Please enter a search term")
            return

        # Update UI
        search_screen = self.sm.get_screen('search')
        search_screen.is_searching = True
        search_screen.status_text = f"Searching for '{query}'..."

        # Run search in background
        thread = threading.Thread(
            target=self._do_search,
            args=(query, media_type),
            daemon=True
        )
        thread.start()

    def _do_search(self, query: str, media_type: str):
        """Background search task."""
        try:
            results, has_more = self.api.search(query, page=1, media_type=media_type)

            # Update UI on main thread
            Clock.schedule_once(
                partial(self._on_search_complete, results, has_more),
                0
            )
        except Exception as e:
            Clock.schedule_once(
                partial(self._on_search_error, str(e)),
                0
            )

    def _on_search_complete(self, results, has_more, dt):
        """Handle search completion on main thread."""
        search_screen = self.sm.get_screen('search')
        search_screen.is_searching = False

        if not results:
            search_screen.status_text = "No results found"
            return

        # Store results and switch to results screen
        self.search_results = results
        results_screen = self.sm.get_screen('results')
        results_screen.results = [
            {
                'nasa_id': item.nasa_id,
                'title': item.title,
                'description': item.description[:200] + '...' if len(item.description) > 200 else item.description,
                'media_type': item.media_type,
            }
            for item in results
        ]
        results_screen.has_more = has_more

        self.sm.current = 'results'

    def _on_search_error(self, error: str, dt):
        """Handle search error on main thread."""
        search_screen = self.sm.get_screen('search')
        search_screen.is_searching = False
        search_screen.status_text = f"Search failed: {error}"

    def download_item(self, nasa_id: str):
        """Queue an item for download."""
        # Find item in results
        item = None
        for result in self.search_results:
            if result.nasa_id == nasa_id:
                item = result
                break

        if not item:
            self.show_error("Item not found")
            return

        # Get asset URLs
        urls = self.api.get_asset_urls(nasa_id)
        if not urls:
            self.show_error("No downloadable assets found")
            return

        # Get settings
        settings_screen = self.sm.get_screen('settings')
        qualities = [settings_screen.selected_quality]

        # Find quality URLs
        quality_urls = find_quality_urls(urls, qualities, item.media_type)

        # Add to download queue
        for quality, url_list in quality_urls.items():
            for url in url_list:
                ext = '.mp4' if item.media_type == 'video' else '.jpg'
                for e in VIDEO_EXTENSIONS:
                    if url.lower().endswith(e):
                        ext = e
                        break

                filename = f"{item.nasa_id}_{quality}{ext}"
                dest = Path(self.download_path) / item.media_type / filename

                self.download_queue.append({
                    'url': url,
                    'dest': str(dest),
                    'item': item,
                    'quality': quality,
                })

        # Start download if not already running
        if not self.is_downloading and self.download_queue:
            self.start_downloads()

    def start_downloads(self):
        """Start processing download queue."""
        if self.is_downloading:
            return

        self.is_downloading = True
        self.sm.current = 'download'

        download_screen = self.sm.get_screen('download')
        download_screen.total_files = len(self.download_queue)
        download_screen.completed_files = 0
        download_screen.progress = 0

        # Start download thread
        thread = threading.Thread(target=self._process_downloads, daemon=True)
        thread.start()

    def _process_downloads(self):
        """Process download queue in background."""
        while self.download_queue:
            item = self.download_queue.pop(0)

            # Update UI
            Clock.schedule_once(
                partial(self._update_download_ui, item['dest']),
                0
            )

            # Download file
            success = download_file(item['url'], Path(item['dest']))

            # Update progress
            Clock.schedule_once(
                partial(self._on_file_complete, success),
                0
            )

        # Download complete
        Clock.schedule_once(self._on_downloads_complete, 0)

    def _update_download_ui(self, filename, dt):
        """Update download UI on main thread."""
        download_screen = self.sm.get_screen('download')
        download_screen.current_file = os.path.basename(filename)
        download_screen.download_status = f"Downloading {download_screen.current_file}"

    def _on_file_complete(self, success, dt):
        """Handle file download completion."""
        download_screen = self.sm.get_screen('download')
        download_screen.completed_files += 1
        download_screen.progress = int(
            (download_screen.completed_files / download_screen.total_files) * 100
        )

    def _on_downloads_complete(self, dt):
        """Handle all downloads complete."""
        self.is_downloading = False
        download_screen = self.sm.get_screen('download')
        download_screen.download_status = "Downloads complete!"
        download_screen.progress = 100

    def show_error(self, message: str):
        """Show error popup."""
        popup = Popup(
            title='Error',
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()

    def go_home(self):
        """Navigate to home screen."""
        self.sm.current = 'search'

    def go_settings(self):
        """Navigate to settings screen."""
        self.sm.current = 'settings'

    def on_stop(self):
        """Clean up when app stops."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass


def main():
    """Main entry point."""
    NasaDownloaderApp().run()


if __name__ == '__main__':
    main()
