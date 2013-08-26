from __future__ import unicode_literals

import gc
import mock
import unittest

import spotify


@mock.patch('spotify.search.lib', spec=spotify.lib)
class SearchResultTest(unittest.TestCase):
    def create_session(self, lib_mock):
        session = mock.sentinel.session
        session._sp_session = mock.sentinel.sp_session
        spotify.session_instance = session
        return session

    def tearDown(self):
        spotify.session_instance = None

    def test_search(self, lib_mock):
        session = self.create_session(lib_mock)
        sp_search = spotify.ffi.cast('sp_search *', spotify.ffi.new('int *'))
        lib_mock.sp_search_create.return_value = sp_search

        result = spotify.SearchResult('alice')

        lib_mock.sp_search_create.assert_called_with(
            session._sp_session, mock.ANY,
            0, 20, 0, 20, 0, 20, 0, 20,
            int(spotify.SearchType.STANDARD), mock.ANY, mock.ANY)
        self.assertEqual(
            spotify.ffi.string(lib_mock.sp_search_create.call_args[0][1]),
            b'alice')
        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 0)
        self.assertIsInstance(result, spotify.SearchResult)

        self.assertFalse(result.complete_event.is_set())
        search_complete_cb = lib_mock.sp_search_create.call_args[0][11]
        userdata = lib_mock.sp_search_create.call_args[0][12]
        search_complete_cb(sp_search, userdata)
        self.assertTrue(result.complete_event.wait(3))

    def test_search_with_callback(self, lib_mock):
        self.create_session(lib_mock)
        sp_search = spotify.ffi.cast('sp_search *', spotify.ffi.new('int *'))
        lib_mock.sp_search_create.return_value = sp_search
        callback = mock.Mock()

        result = spotify.SearchResult('alice', callback=callback)

        search_complete_cb = lib_mock.sp_search_create.call_args[0][11]
        userdata = lib_mock.sp_search_create.call_args[0][12]
        search_complete_cb(sp_search, userdata)

        result.complete_event.wait(3)
        callback.assert_called_with(result)

    def test_search_where_result_is_gone_before_callback_is_called(
            self, lib_mock):
        self.create_session(lib_mock)
        sp_search = spotify.ffi.cast('sp_search *', spotify.ffi.new('int *'))
        lib_mock.sp_search_create.return_value = sp_search
        callback = mock.Mock()

        result = spotify.SearchResult('alice', callback=callback)
        complete_event = result.complete_event
        result = None  # noqa
        gc.collect()  # Needed for PyPy

        search_complete_cb = lib_mock.sp_search_create.call_args[0][11]
        userdata = lib_mock.sp_search_create.call_args[0][12]
        search_complete_cb(sp_search, userdata)

        complete_event.wait(3)
        self.assertEqual(callback.call_count, 1)
        self.assertEqual(callback.call_args[0][0]._sp_search, sp_search)

    def assert_fails_if_error(self, lib_mock, func):
        lib_mock.sp_search_error.return_value = (
            spotify.ErrorType.BAD_API_VERSION)
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        self.assertRaises(spotify.Error, func, search)

    def test_adds_ref_to_sp_search_when_created(self, lib_mock):
        sp_search = spotify.ffi.new('int *')

        spotify.SearchResult(sp_search=sp_search)

        lib_mock.sp_search_add_ref.assert_called_with(sp_search)

    def test_releases_sp_search_when_search_dies(self, lib_mock):
        sp_search = spotify.ffi.new('int *')

        search = spotify.SearchResult(sp_search=sp_search)
        search = None  # noqa
        gc.collect()  # Needed for PyPy

        lib_mock.sp_search_release.assert_called_with(sp_search)

    def test_complete_event_is_unset_by_default(self, lib_mock):
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        self.assertFalse(search.complete_event.is_set())

    def test_is_loaded(self, lib_mock):
        lib_mock.sp_search_is_loaded.return_value = 1
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.is_loaded

        lib_mock.sp_search_is_loaded.assert_called_once_with(sp_search)
        self.assertTrue(result)

    def test_error(self, lib_mock):
        lib_mock.sp_search_error.return_value = int(
            spotify.ErrorType.IS_LOADING)
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.error

        lib_mock.sp_search_error.assert_called_once_with(sp_search)
        self.assertIs(result, spotify.ErrorType.IS_LOADING)

    @mock.patch('spotify.utils.load')
    def test_load(self, load_mock, lib_mock):
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        search.load(10)

        load_mock.assert_called_with(search, timeout=10)

    @mock.patch('spotify.track.lib', spec=spotify.lib)
    def test_tracks(self, track_lib_mock, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        sp_track = spotify.ffi.cast('sp_track *', spotify.ffi.new('int *'))
        lib_mock.sp_search_num_tracks.return_value = 1
        lib_mock.sp_search_track.return_value = sp_track
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 1)
        result = search.tracks
        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 2)

        self.assertEqual(len(result), 1)
        lib_mock.sp_search_num_tracks.assert_called_with(sp_search)

        item = result[0]
        self.assertIsInstance(item, spotify.Track)
        self.assertEqual(item._sp_track, sp_track)
        self.assertEqual(lib_mock.sp_search_track.call_count, 1)
        lib_mock.sp_search_track.assert_called_with(sp_search, 0)
        track_lib_mock.sp_track_add_ref.assert_called_with(sp_track)

    def test_tracks_if_no_tracks(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_num_tracks.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.tracks

        self.assertEqual(len(result), 0)
        lib_mock.sp_search_num_tracks.assert_called_with(sp_search)
        self.assertEqual(lib_mock.sp_search_track.call_count, 0)

    def test_tracks_if_unloaded(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_is_loaded.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.tracks

        lib_mock.sp_search_is_loaded.assert_called_with(sp_search)
        self.assertEqual(len(result), 0)

    def test_tracks_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.tracks)

    @mock.patch('spotify.album.lib', spec=spotify.lib)
    def test_albums(self, album_lib_mock, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        sp_album = spotify.ffi.cast('sp_album *', spotify.ffi.new('int *'))
        lib_mock.sp_search_num_albums.return_value = 1
        lib_mock.sp_search_album.return_value = sp_album
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 1)
        result = search.albums
        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 2)

        self.assertEqual(len(result), 1)
        lib_mock.sp_search_num_albums.assert_called_with(sp_search)

        item = result[0]
        self.assertIsInstance(item, spotify.Album)
        self.assertEqual(item._sp_album, sp_album)
        self.assertEqual(lib_mock.sp_search_album.call_count, 1)
        lib_mock.sp_search_album.assert_called_with(sp_search, 0)
        album_lib_mock.sp_album_add_ref.assert_called_with(sp_album)

    def test_albums_if_no_albums(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_num_albums.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.albums

        self.assertEqual(len(result), 0)
        lib_mock.sp_search_num_albums.assert_called_with(sp_search)
        self.assertEqual(lib_mock.sp_search_album.call_count, 0)

    def test_albums_if_unloaded(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_is_loaded.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.albums

        lib_mock.sp_search_is_loaded.assert_called_with(sp_search)
        self.assertEqual(len(result), 0)

    def test_albums_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.albums)

    @mock.patch('spotify.artist.lib', spec=spotify.lib)
    def test_artists(self, artist_lib_mock, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        sp_artist = spotify.ffi.cast('sp_artist *', spotify.ffi.new('int *'))
        lib_mock.sp_search_num_artists.return_value = 1
        lib_mock.sp_search_artist.return_value = sp_artist
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 1)
        result = search.artists
        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 2)

        self.assertEqual(len(result), 1)
        lib_mock.sp_search_num_artists.assert_called_with(sp_search)

        item = result[0]
        self.assertIsInstance(item, spotify.Artist)
        self.assertEqual(item._sp_artist, sp_artist)
        self.assertEqual(lib_mock.sp_search_artist.call_count, 1)
        lib_mock.sp_search_artist.assert_called_with(sp_search, 0)
        artist_lib_mock.sp_artist_add_ref.assert_called_with(sp_artist)

    def test_artists_if_no_artists(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_num_artists.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.artists

        self.assertEqual(len(result), 0)
        lib_mock.sp_search_num_artists.assert_called_with(sp_search)
        self.assertEqual(lib_mock.sp_search_artist.call_count, 0)

    def test_artists_if_unloaded(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_is_loaded.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.artists

        lib_mock.sp_search_is_loaded.assert_called_with(sp_search)
        self.assertEqual(len(result), 0)

    def test_artists_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.artists)

    @mock.patch('spotify.playlist.lib', spec=spotify.lib)
    def test_playlists(self, playlist_lib_mock, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_num_playlists.return_value = 1
        lib_mock.sp_search_playlist_name.return_value = spotify.ffi.new(
            'char[]', b'The Party List')
        lib_mock.sp_search_playlist_uri.return_value = spotify.ffi.new(
            'char[]', b'spotify:playlist:foo')
        lib_mock.sp_search_playlist_image_uri.return_value = spotify.ffi.new(
            'char[]', b'spotify:image:foo')
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 1)
        result = search.playlists
        self.assertEqual(lib_mock.sp_search_add_ref.call_count, 2)

        self.assertEqual(len(result), 1)
        lib_mock.sp_search_num_playlists.assert_called_with(sp_search)

        item = result[0]
        self.assertIsInstance(item, spotify.SearchResultPlaylist)
        self.assertEqual(item.name, 'The Party List')
        self.assertEqual(item.uri, 'spotify:playlist:foo')
        self.assertEqual(item.image_uri, 'spotify:image:foo')
        self.assertEqual(lib_mock.sp_search_playlist_name.call_count, 1)
        lib_mock.sp_search_playlist_name.assert_called_with(sp_search, 0)
        self.assertEqual(lib_mock.sp_search_playlist_uri.call_count, 1)
        lib_mock.sp_search_playlist_uri.assert_called_with(sp_search, 0)
        self.assertEqual(lib_mock.sp_search_playlist_image_uri.call_count, 1)
        lib_mock.sp_search_playlist_image_uri.assert_called_with(sp_search, 0)

    def test_playlists_if_no_playlists(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_num_playlists.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.playlists

        self.assertEqual(len(result), 0)
        lib_mock.sp_search_num_playlists.assert_called_with(sp_search)
        self.assertEqual(lib_mock.sp_search_playlist.call_count, 0)

    def test_playlists_if_unloaded(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_is_loaded.return_value = 0
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.playlists

        lib_mock.sp_search_is_loaded.assert_called_with(sp_search)
        self.assertEqual(len(result), 0)

    def test_playlists_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.playlists)

    def test_query(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_query.return_value = spotify.ffi.new(
            'char[]', b'Foo Bar Baz')
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.query

        lib_mock.sp_search_query.assert_called_once_with(sp_search)
        self.assertEqual(result, 'Foo Bar Baz')

    def test_query_is_none_if_empty(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_query.return_value = spotify.ffi.new('char[]', b'')
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.query

        lib_mock.sp_search_query.assert_called_once_with(sp_search)
        self.assertIsNone(result)

    def test_query_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.query)

    def test_did_you_mean(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_did_you_mean.return_value = spotify.ffi.new(
            'char[]', b'Foo Bar Baz')
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.did_you_mean

        lib_mock.sp_search_did_you_mean.assert_called_once_with(sp_search)
        self.assertEqual(result, 'Foo Bar Baz')

    def test_did_you_mean_is_none_if_empty(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_did_you_mean.return_value = spotify.ffi.new(
            'char[]', b'')
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.did_you_mean

        lib_mock.sp_search_did_you_mean.assert_called_once_with(sp_search)
        self.assertIsNone(result)

    def test_did_you_mean_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.did_you_mean)

    def test_total_tracks(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_total_tracks.return_value = 75
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.total_tracks

        lib_mock.sp_search_total_tracks.assert_called_with(sp_search)
        self.assertEqual(result, 75)

    def test_total_tracks_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.total_tracks)

    def test_total_albums(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_total_albums.return_value = 75
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.total_albums

        lib_mock.sp_search_total_albums.assert_called_with(sp_search)
        self.assertEqual(result, 75)

    def test_total_albums_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.total_albums)

    def test_total_artists(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_total_artists.return_value = 75
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.total_artists

        lib_mock.sp_search_total_artists.assert_called_with(sp_search)
        self.assertEqual(result, 75)

    def test_total_artists_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.total_artists)

    def test_total_playlists(self, lib_mock):
        lib_mock.sp_search_error.return_value = spotify.ErrorType.OK
        lib_mock.sp_search_total_playlists.return_value = 75
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.total_playlists

        lib_mock.sp_search_total_playlists.assert_called_with(sp_search)
        self.assertEqual(result, 75)

    def test_total_playlists_fails_if_error(self, lib_mock):
        self.assert_fails_if_error(lib_mock, lambda s: s.total_playlists)

    @mock.patch('spotify.Link', spec=spotify.Link)
    def test_link_creates_link_to_search(self, link_mock, lib_mock):
        link_mock.return_value = mock.sentinel.link
        sp_search = spotify.ffi.new('int *')
        search = spotify.SearchResult(sp_search=sp_search)

        result = search.link

        link_mock.assert_called_once_with(search)
        self.assertEqual(result, mock.sentinel.link)


class SearchTypeTest(unittest.TestCase):

    def test_has_constants(self):
        self.assertEqual(spotify.SearchType.STANDARD, 0)
        self.assertEqual(spotify.SearchType.SUGGEST, 1)
