#!/usr/bin/python -i
# (c) 2015 Taeyeon Mori
# Use this with python -i to play with the data structures plex returns

import sys
import logging
from pprint import pprint

import lxml.etree

import comPlex.client
import comPlex.connection
import comPlex.library

if len(sys.argv) < 2:
    print("Please add the server host to the command line")
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG)


def _getxml(xml):
    if isinstance(xml, comPlex.library.XmlItem):
        return xml.xml
    return xml


def xprint(xml):
    xml = _getxml(xml)
    for node in xml.iter():
        node.tail = "\n"
    print(lxml.etree.tostring(xml, pretty_print=True, encoding="unicode"))


def aprint(xml):
    pprint(dict(_getxml(xml).attrib))


class CPGuiClient(comPlex.client.Client):
    Device = "VLC"


# decided by dice-roll: guaranteed to be random ;)
client = CPGuiClient(client_id='e1b7402b-b592-4b25-a170-b69646811338')
conn = comPlex.connection.Connection(client, host=sys.argv[1])

conn.refresh()

sections = conn.get_sections()
# pprint(sections)

items = sections[0].get_items()
# pprint(items)

seasons = items[-1].get_children()
# pprint(seasons)

episodes = seasons[0].get_children()
# pprint(episodes)

# print("Ep1 url: %s" % conn.get_url(episodes[0].get_formats()[0].get_parts()[0].path))

print("Vars: client, conn, sections[], items[], seasons[], episodes[]")
print("Fns : pprint(), aprint(), xprint()")
