#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================

class XmlObject:
    def __init__(self, conn, xml):
        self.connection = conn
        self.xml = xml


class XmlAttrib:
    def __init__(self, name, fallback=None, type=None):
        self.name = name
        self.fallback = fallback
        self.type = type

    def __get__(self, owner, _=None, *, _fallback=object()):
        if owner is None:
            return self
        res = owner.xml.get(self.name, _fallback)
        if res is _fallback:
            return self.fallback
        elif self.type:
            return self.type(res)
        else:
            return res

    def __set__(self, owner, value):
        owner.xml.set(self.name, str(value))
