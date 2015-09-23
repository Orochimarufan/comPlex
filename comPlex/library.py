#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================

from .dt import XmlAttrib, XmlObject as XmlItem


class XmlLibraryItem(XmlItem):
    _key = XmlAttrib("key")

    @property
    def key(self):
        # XXX: does this always apply? /library/<x>/<key>/...
        key = self.xml.get("key")
        return key if not key.startswith('/') else key.split('/')[3]

    @property
    def path(self):
        return "/library/metadata/%s" % self.key

    title = XmlAttrib("title", "Title Unknown")
    thumbnail_path = XmlAttrib("thumb")
    summary = XmlAttrib("summary")
    type = XmlAttrib("type")


class BaseContainer(XmlLibraryItem):
    size = XmlAttrib("childCount", type=int)

    def __init__(self, conn, xml):
        super().__init__(conn, xml)
        self._children_xml = None

    def __repr__(self):
        return "<Plex %s %s '%s' (%s) on '%s'>" % (
            self.type.capitalize() if self.type else "(unknown type)",
            type(self).__name__,
            self.title,
            self.key,
            self.connection.name,
        )

    @property
    def children_xml(self):
        if self._children_xml is None:
            self._children_xml = self.connection.xml(self.children_xml_path).getroot()
        return self._children_xml

    def get_children(self):
        return [create_item(self.connection, child)
                for child in self.children_xml]

    def __getitem__(self, item):
        if isinstance(item, slice):
            return [create_item(self.connection, child)
                    for child in self.children_xml.__getitem__(item)]
        else:
            return create_item(self.connection, self.children_xml[item])


class Container(BaseContainer):
    leafCount = XmlAttrib("leafCount", -1, int)
    viewedCount = XmlAttrib("viewedLeafCount", 0, int)
    year = XmlAttrib("year", 0, int)
    rating = XmlAttrib("rating", 0.0, float)

    children_xml_path = XmlAttrib("key")


class Section(BaseContainer):
    title = XmlAttrib("title", "Unknown Section")
    uuid = XmlAttrib("uuid", "")

    @property
    def path(self):
        return "/library/sections/%s" % self._key

    @property
    def children_xml_path(self):
        return self.path + "/all"

    def get_items(self, key="all"):
        return [create_item(self.connection, child)
                for child in self.connection.xml(self.path + "/" + key).getroot()]

    def refresh(self):
        return self.connection.ping('/library/sections/%s/refresh' % self._key)


class Video(XmlLibraryItem):
    key = XmlAttrib("ratingKey")

    duration = XmlAttrib("duration", type=int)
    index = XmlAttrib("index", type=int)
    date = XmlAttrib("originallyAvailableAt")
    rating = XmlAttrib("rating", type=float)
    views = XmlAttrib("viewCount", 0, type=int)

    def __repr__(self):
        return "<Plex %s Video '%s' (%s) from on %s>" % (
            self.type.capitalize() if self.type else "",
            self.title,
            self.key,
            self.connection.name,
        )

    def get_formats(self):
        return [Media(self, media, i) for i, media in enumerate(self.xml.iterchildren("Media"))]

    def mark_watched(self):
        self.views += 1
        return self.connection.ping('/:/scrobble?key=%s&identifier=com.plexapp.plugins.library' % self.key)

    def mark_unwatched(self):
        self.views = 0
        return self.connection.ping('/:/unscrobble?key=%s&identifier=com.plexapp.plugins.library' % self.key)


class Media(XmlItem):
    # General
    id = XmlAttrib("id")
    duration = XmlAttrib("duration", type=int)
    container = XmlAttrib("container")

    # Video
    video_aspect_ratio = XmlAttrib("aspectRatio", type=float)
    video_bitrate = XmlAttrib("bitrate", type=int)
    video_height = XmlAttrib("height", type=int)
    video_width = XmlAttrib("width", type=int)
    video_codec = XmlAttrib("videoCodec")
    video_framerate = XmlAttrib("videoFrameRate")
    video_resolution = XmlAttrib("videoResolution")

    # Audio
    audio_channels = XmlAttrib("audioChannels", type=int)
    audio_codec = XmlAttrib("audioCodec")

    def __init__(self, video, xml, index):
        super().__init__(video.connection, xml)
        self.video = video
        self.index = index

    def __repr__(self):
        return "<Plex Media %s %s(%.1f min A(%dch %s) V(%dkb/s %dx%d %s @%s fps)) on %s>" % (
            self.id,
            self.container,
            self.duration / 60000,
            self.audio_channels,
            self.audio_codec,
            self.video_bitrate,
            self.video_width, self.video_height,
            self.video_codec,
            self.video_framerate,
            self.connection.name,
        )

    def get_parts(self):
        return [MediaPart(self, part, i) for i, part in enumerate(self.xml)]


class MediaPart(XmlItem):
    id = XmlAttrib("id")

    duration = XmlAttrib("duration", type=int)
    size = XmlAttrib("size", type=int)

    fs_path = XmlAttrib("file")
    path = XmlAttrib("key")

    def __init__(self, media, xml, index):
        super().__init__(media.connection, xml)
        self.media = media
        self.index = index


def create_item(conn, xml):
    return {
        "Directory": Container,
        "Video": Video,
    }[xml.tag](conn, xml)
