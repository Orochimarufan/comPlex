#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================


import uuid
import socket
import platform

import requests

from .transcode import TranscodeSession
from . import __version__


class Client:
    """
    Holds information about the client application
    """
    # Should be handled in subclasses
    Device = "comPlex client"
    Product = "unknown"
    Model = platform.platform()
    Version = "unknown"
    Language = "en"
    Provides = "player"

    @property
    def DeviceName(self):
        return socket.gethostbyaddr(socket.gethostname())[0]

    @property
    def ClientIdentifier(self):
        if self.client_id is None:
            self.client_id = str(uuid.uuid4())
        return self.client_id

    # Platform information
    Platform = "comPlex"
    ClientPlatform = "comPlex"
    PlatformVersion = __version__

    # -----------------------------------
    def __init__(self, client_id=None):
        self.client_id = client_id

        self.session = requests.Session()

    @property
    def plex_headers(self):
        return {"X-Plex-" + name: getattr(self, name.replace("-", ""))
                for name in ("Device", "Product", "Model", "Device-Name",
                             "Version", "Language", "Provides", "Client-Identifier",
                             "Platform", "Client-Platform", "Platform-Version")}

    def setup_transcode(self, conn, url, options):
        return TranscodeSession(conn, url)
