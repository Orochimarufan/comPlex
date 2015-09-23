#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================

import urllib.parse


class ConnectedObject:
    def __init__(self, connection):
        self.connection = connection


class TF_Meta(type):
    def __init__(cls, name, bases, body):
        super().__init__(name, bases, body)
        if "transform" not in cls.__dict__:
            cls.transform = {}


class AbstractTransformAttrib(metaclass=TF_Meta):
    def __transform_get(self, value):
        if self.type in self.transform:
            return self.transform[self.type][0](value)
        else:
            return self.type(value)

    def __transform_set(self, value):
        if self.type in self.transform:
            return self.transform[self.type][1](value)
        else:
            return str(value)

    @staticmethod
    def __transform_not(value):
        return value

    def __init__(self, type=None, fallback=None):
        self.type = type
        self.fallback = fallback

        if type is None:
            self.transform_get = self.__transform_not
            self.transform_set = self.__transform_not
        else:
            self.transform_get = self.__transform_get
            self.transform_set = self.__transform_set

    def __get__(self, owner, _=None, *, _fallback=object()):
        if owner is None:
            return self
        res = self.get(owner, _fallback)
        return self.fallback if res is _fallback else self.transform_get(res)

    def __set__(self, owner, value):
        self.set(owner, self.transform_set(value))

        # abstract def get(self, owner, fallback)
        # abstract def set(self, owner, value)


class TransformAttrib(AbstractTransformAttrib):
    def __init__(self, name, type=None, fallback=None):
        super().__init__(type, fallback)
        self.name = name

    def get(self, owner, fallback):
        return getattr(owner, self.name, fallback)

    def set(self, owner, value):
        return setattr(owner, self.name, value)


# Objects with XML backing
class XmlObject(ConnectedObject):
    def __init__(self, connection, xml):
        super().__init__(connection)
        self.xml = xml


class XmlAttrib(AbstractTransformAttrib):
    def __init__(self, name, fallback=None, type=None):
        super().__init__(type, fallback)
        self.name = name

    def get(self, owner, fallback):
        return owner.xml.get(self.name, fallback)

    def set(self, owner, value):
        return owner.xml.set(self.name, value)


# Object representing url-encoded options
class OperationObject(ConnectedObject):
    def __init__(self, connection):
        super().__init__(connection)
        self.options = {}

    def urlencode(self):
        return urllib.parse.urlencode(self.options)


class OptionAttrib(AbstractTransformAttrib):
    def __init__(self, name, type=None, fallback=None):
        super().__init__(type, fallback)
        self.name = name

    def get(self, owner, fallback):
        return owner.options.get(self.name, fallback)

    def set(self, owner, value):
        owner.options[self.name] = value
