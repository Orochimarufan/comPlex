#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================

import logging
import posixpath

try:
    from lxml import etree
except ImportError:
    from xml.etree import ElementTree as etree

import requests

from .library import Section, create_item
from .client import Client

logger = logging.getLogger("comPlex.connection")


# Exceptions
class ConnectionError(Exception):
    pass


class OfflineError(ConnectionError):
    pass


class UnauthorizedError(ConnectionError):
    pass


class InvalidResponseError(ConnectionError):
    pass


class Connection:
    def __init__(self, client: Client, uuid=None, name=None, host=None, port=32400, token=None, discovery=None):
        self.client = client

        self.uuid = uuid
        self.name = name
        self.host = host
        self.port = port

        if discovery == "myplex":
            self.public_host = host
            self.public_port = port
        else:
            self.public_host = None
            self.public_port = None

        self.token = token

        self.protocol = "http"

        self.owned = 0
        self.master = 0
        self.class_type = "primary"
        self.plex_home_enabled = False
        self.discovered = False

    def get_url(self, path, *, relative_to="/"):
        return "%s://%s:%d%s" % (self.protocol, self.host, self.port, posixpath.join(relative_to, path))

    def _request(self, method, path, *, valid_codes=(requests.codes.ok,), **kwargs):
        try:
            response = self.client.session.request(
                method,
                self.get_url(path),
                params=self.client.plex_headers,
                **kwargs
            )
        except requests.exceptions.ConnectionError as e:
            logger.error("Host %s is offline or uncontactable. error: %s" % (self.host, e))
            raise OfflineError(e)
        except requests.exceptions.ReadTimeout as e:
            logger.error("Timeout for '%s' on Host %s" % (path, self.host))
            raise OfflineError(e)
        else:
            if response.status_code in valid_codes:
                return response
            elif response.status_code == requests.codes.unauthorized:
                logger.warn("Got 401 Unauthorized - Please log into myplex and check your password")
                raise UnauthorizedError()
            else:
                logger.error("Got unexpected status code for '%s' on %s: %s" % (path, self.host, response.status_code))
                raise InvalidResponseError()

    def xml(self, path, *, method="GET"):
        response = self._request(method, path, stream=True)
        # requests + etree = magic!
        response.raw.decode_content = True
        tree = etree.parse(response.raw)
        response.close()
        return tree

    def ping(self, path, *, method="GET"):
        return bool(self._request(method, path))

    def refresh(self):
        try:
            tree = self.xml("/").getroot()
        except ConnectionError:
            self.discovered = False
            return False
        else:
            self.name = tree.get('friendlyName')
            self.uuid = tree.get('machineIdentifier')
            self.owned = 1
            self.master = 1
            self.class_type = tree.get('serverClass', 'primary')
            self.plex_home_enabled = tree.get('multiuser') == '1'
            self.discovered = True
            return True

    def get_sections(self):
        return [Section(self, section) for section in self.xml("/library/sections").getroot()]

    def get_item(self, key):
        return create_item(self, self.xml("/library/metadata/%s" % key).getroot())

    def get_metadata(self, id):
        return self.xml('/library/metadata/%s' % id)

    def get_universal_transcode(self, url, **kwds):
        return self.client.setup_transcode(url, kwds)
