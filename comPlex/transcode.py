#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================

from uuid import uuid4
import urllib.parse

from .dt import OperationObject, OptionAttrib


class TranscodeSession(OperationObject):
    def __init__(self, conn, session=None, ext="ts", **opts):
        super().__init__(conn)

        if session is None:
            session = uuid4()

        self.options.update(opts)
        self.options["session"] = session

        self.ext = ext

    uuid = OptionAttrib("session")

    @property
    def path(self):
        parms = dict(self.connection.client.plex_headers)
        parms.update(self.options)
        return "/video/:/transcode/universal/start.%s?%s" % (self.ext, urllib.parse.urlencode(parms))

    @property
    def url(self):
        return self.connection.get_url(self.path)

    def stop(self):
        return self.connection.ping('/video/:/transcode/universal/stop?session=%s' % self.uuid)

    @classmethod
    def from_library(cls, video, session=None, ext="ts", **b):
        return cls(video.connection, session, ext, path="http://127.0.0.1:32400%s" % video.path, **b)
