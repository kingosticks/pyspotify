from __future__ import unicode_literals

from spotify import ffi, ImageSize, lib
from spotify.utils import load, to_bytes, to_unicode


__all__ = [
    'Artist',
]


class Artist(object):
    """A Spotify artist."""

    def __init__(self, sp_artist):
        lib.sp_artist_add_ref(sp_artist)
        self.sp_artist = ffi.gc(sp_artist, lib.sp_artist_release)

    @property
    def name(self):
        """The artist's name.

        Will always return :class:`None` if the artist isn't loaded.
        """
        name = to_unicode(lib.sp_artist_name(self.sp_artist))
        return name if name else None

    @property
    def is_loaded(self):
        """Whether the artist's data is loaded."""
        return bool(lib.sp_artist_is_loaded(self.sp_artist))

    def load(self, timeout=None):
        """Block until the artist's data is loaded.

        :param timeout: seconds before giving up and raising an exception
        :type timeout: float
        :returns: self
        """
        return load(self, timeout=timeout)

    def portrait_id(self, image_size=ImageSize.NORMAL):
        """The artist's portrait image ID as a bytestring.

        ``image_size`` is an :class:`ImageSize` value, by default
        :attr:`ImageSize.NORMAL`.

        Will always return :class:`None` if the artist isn't loaded or the
        artist has no portrait.
        """
        portrait_id = lib.sp_artist_portrait(self.sp_artist, image_size)
        return to_bytes(portrait_id) if portrait_id != ffi.NULL else None

    # TODO Add portrait() helper that returns the image directly

    @property
    def link(self):
        """A :class:`Link` to the artist."""
        from spotify.link import Link
        return Link(self)