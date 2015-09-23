#!/usr/bin/python
# ======================================================================
# Plex Media Server protocol
# ======================================================================
# (c) 2015      Taeyeon Mori <orochimarufan.x3@gmail.com>
# ======================================================================
# NOTE: this code is not written with configurability in mind (yet)

import os
import sys
import logging
import time
import uuid

from PyQt5 import QtCore, QtGui, QtWidgets

from .library import BaseContainer, Video, Container
from .connection import Connection, ConnectionError
from .client import Client
from .transcode import TranscodeSession
from . import __version__

CACHE_PATH = "/tmp/comPlex"  # TODO: globals are bad


class Item:
    __slots__ = "data"

    def __init__(self, data, parent=None, row=0):
        # logging.debug("Item %s" % data)
        self.data = data
        self.parent = parent
        self.children = {}
        self.row = row

    def __eq__(self, other):
        return self.data is other.data


class ChildItem(Item):
    KeepImageInMemory = False

    def __init__(self, data, parent=None, row=0):
        super().__init__(data, parent, row)
        self.conn = data.connection

        if data.thumbnail_path:
            self.ifile = os.path.join(CACHE_PATH, self.conn.name, data.thumbnail_path.replace("/", "+"))
        else:
            self.ifile = None

        self._image = None

    def title(self):
        return self.data.title

    def image(self):
        if self._image is not None:
            return self._image
        elif not self.ifile:
            return None
        elif os.path.isfile(self.ifile):
            img = QtGui.QPixmap(self.ifile)
        else:
            try:
                res = self.conn._request("GET", self.data.thumbnail_path)
            except ConnectionError:
                return
            else:
                with open(self.ifile, "wb") as f:
                    f.write(res.content)
                img = QtGui.QPixmap.fromImage(QtGui.QImage.fromData(res.content))

        # Scale
        image = img.scaledToHeight(100)

        if self.KeepImageInMemory:
            self._image = image

        return image

    tooltip = title

    def __eq__(self, other):
        return self.data is other.data or hasattr(other.data, "_key") and self.data._key == other.data._key


class ServerItem(Item):
    def __init__(self, data, parent=None, row=0):
        super().__init__(data, parent, row)
        self.items = data.get_sections()

    def get_child(self, row):
        if row not in self.children:
            self.children[row] = ContainerItem(self.items[row], self, row)
        return self.children[row]

    def size(self):
        return len(self.items)

    def has_children(self):
        return True

    def title(self):
        return self.data.name


class ContainerItem(ChildItem):
    def get_child(self, row):
        if row not in self.children:
            it = self.data[row]
            if isinstance(it, BaseContainer):
                ci = ContainerItem(it, self, row)
            else:
                ci = FileItem(it, self, row)
            self.children[row] = ci
        return self.children[row]

    def size(self):
        return sum(1 for x in self.data.children_xml.iterchildren("Directory", "Video"))

    def has_children(self):
        return self.data.size is None or self.data.size > 0

    def unfinished(self):
        return False  # TODO

    def tooltip(self):
        if isinstance(self.data, Container):
            return "%s (%4d, %s%dEps, %1.1f)" % (
                self.data.title,
                self.data.year,
                ("%d/" % self.data.viewedCount if self.data.viewedCount else ""),
                self.data.leafCount,
                self.data.rating,
            )
        else:
            return self.data.title


class FileItem(ChildItem):
    def size(self):
        return 0

    def has_children(self):
        return False

    def get_child(self, row):
        return None

    def unfinished(self):
        return self.data.views == 0


class PlexModel(QtCore.QAbstractItemModel):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.get_child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QtCore.QModelIndex()

    def parent(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return QtCore.QModelIndex()

        item = index.internalPointer().parent
        if item == self.root or item is None:
            return QtCore.QModelIndex()
        else:
            return self.createIndex(item.row, 0, item)

    def hasChildren(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            return True
        return parent.internalPointer().has_children()

    def rowCount(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            return self.root.size()
        return parent.internalPointer().size()

    def columnCount(self, parent=None):
        return 1

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            ip = index.internalPointer()
            if index.column() == 0:
                if role == QtCore.Qt.DisplayRole:
                    return ("*" if ip.unfinished() else "") + ip.title()
                elif role == QtCore.Qt.ToolTipRole:
                    return ip.tooltip()
                elif role == QtCore.Qt.DecorationRole:
                    return ip.image()


class FlatProxy(QtCore.QAbstractProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent_index = QtCore.QModelIndex()

    def setParentIndex(self, ix):
        self.modelAboutToBeReset.emit()
        self.parent_index = ix
        self.modelReset.emit()

    def mapFromSource(self, index):
        return self.createIndex(index.row(), index.column(), None)

    def mapToSource(self, index):
        return self.sourceModel().index(index.row(), index.column(), self.parent_index)

    def columnCount(self, parent=None):
        return self.sourceModel().columnCount(self.parent_index)

    def rowCount(self, parent=None):
        return self.sourceModel().rowCount(self.parent_index)

    def index(self, row, column, parent=None):
        return self.createIndex(row, column, None)

    def parent(self, index):
        return QtCore.QModelIndex()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, conn, parent=None):
        super().__init__(parent)

        self.conn = conn

        self.model = PlexModel(ServerItem(conn), self)
        self.flat_model = FlatProxy(self)
        self.flat_model.setSourceModel(self.model)

        self.force_transcode = False

        self.setupUi()

    def setupUi(self):
        settings = QtCore.QSettings()

        # Window
        self.setWindowTitle(self.conn.name)
        self.resize(800, 600)
        self.move(0, 0)

        settings.beginGroup("GUI")

        # Menu bar
        file = self.menuBar().addMenu("&File")
        quit = file.addAction("&Quit")
        quit.triggered.connect(self.close)

        view = self.menuBar().addMenu("&View")
        refresh = view.addAction("&Refresh")
        refresh.triggered.connect(self.refresh)
        view.addSection("Mode")
        view_mode = QtWidgets.QActionGroup(view)
        icons = view_mode.addAction("&Icons")
        icons.triggered.connect(self.setViewIcons)
        view.addAction(icons)
        list = view_mode.addAction("&List")
        list.triggered.connect(self.setViewList)
        view.addAction(list)
        tree = view_mode.addAction("&Tree")
        tree.triggered.connect(self.setViewTree)
        view.addAction(tree)

        settings_menu = self.menuBar().addMenu("&Settings")
        always_transcode = settings_menu.addAction("Always Request &Transcode")
        always_transcode.setCheckable(True)
        always_transcode.toggled.connect(self.toggleForceTranscode)
        always_transcode.setChecked(settings.value("AlwaysTranscode", False, type=bool))
        keep_thumbs = settings_menu.addAction("Keep thumbnail images in &memory")
        keep_thumbs.setCheckable(True)
        keep_thumbs.toggled.connect(self.toggleKeepThumbs)
        keep_thumbs.setChecked(settings.value("KeepThumbnailsInMemory", False, type=bool))

        # Stacked widget
        # TODO: be smarter about it and convert between views
        self.stack = QtWidgets.QStackedWidget(self)
        self.setCentralWidget(self.stack)

        # Tree View
        view = QtWidgets.QTreeView(self)
        view.setModel(self.model)
        view.activated.connect(self.absItemActivated)
        self.stack.addWidget(view)

        # Flat View
        widget = QtWidgets.QWidget(self)
        grid = QtWidgets.QGridLayout(widget)
        up = QtWidgets.QPushButton("Go up")
        up.clicked.connect(self.relGoUp)
        up.setIcon(QtGui.QIcon.fromTheme("go-up"))
        grid.addWidget(up, 0, 0)
        self.location = QtWidgets.QLabel(self.conn.name)
        grid.addWidget(self.location, 0, 1, 1, 3)
        self.list = QtWidgets.QListView(self)
        self.list.setGridSize(QtCore.QSize(110, 120))
        self.list.setWordWrap(True)
        self.list.setModel(self.flat_model)
        self.list.activated.connect(self.relItemActivated)
        grid.addWidget(self.list, 1, 0, 1, 4)
        self.stack.addWidget(widget)

        icons.setChecked(True)
        self.setViewIcons()

        last_view = settings.value("View", "icons")
        if last_view == "list":
            self.setViewFlat()
        elif last_view == "icons":
            self.setViewIcons()
        elif last_view == "tree":
            self.setViewTree()

        # Status Bar
        self.statusBar().showMessage("Connected to %s" % conn.name)

        settings.endGroup()

    def refresh(self):
        QtWidgets.QMessageBox.critical(self, "Not Implemented",
                                       "Refreshing not supported at this time. Restart the software")

    def setViewIcons(self):
        self.stack.setCurrentIndex(1)
        self.list.setViewMode(QtWidgets.QListView.IconMode)
        self.setSetting("GUI/View", "icons")

    def setViewList(self):
        self.stack.setCurrentIndex(1)
        self.list.setViewMode(QtWidgets.QListView.ListMode)
        self.setSetting("GUI/View", "list")

    def setViewTree(self):
        self.stack.setCurrentIndex(0)
        self.setSetting("Gui/View", "tree")

    def toggleForceTranscode(self, state):
        self.force_transcode = state
        self.setSetting("GUI/AlwaysTranscode", state, "Always Request Transcode")

    def toggleKeepThumbs(self, state):
        ChildItem.KeepImageInMemory = state
        self.setSetting("GUI/KeepThumbnailsInMemory", state, "Keep thumbnails in memory")

    def setSetting(self, key, value, description=None):
        if description is None:
            description = key
        QtCore.QSettings().setValue(key, value)
        if isinstance(value, bool):
            value = "ON" if value else "OFF"
        self.statusBar().showMessage("%s is now %s" % (description, value))

    def absItemActivated(self, ix):
        item = ix.internalPointer().data
        if isinstance(item, Video):
            self.playVideo(item)

    def relItemActivated(self, ix):
        index = self.flat_model.mapToSource(ix)
        item = index.internalPointer().data
        if isinstance(item, Video):
            self.playVideo(item)
        else:
            self.flat_model.setParentIndex(index)
            self.location.setText(self.location.text() + " > " + item.title)

    def relGoUp(self):
        self.flat_model.setParentIndex(self.model.parent(self.flat_model.parent_index))
        if not self.flat_model.parent_index.isValid():
            self.location.setText(self.conn.name)
        else:
            self.location.setText(self.location.text().rsplit(" > ", 1)[0])

    def playVideo(self, video):
        # Figure out what to play
        best_format = None
        best_score = 0
        for format in video.get_formats():
            score = 1000
            if format.video_height > 800:
                score -= 100
            elif format.video_height < 480:
                score -= 100
            if len(format.get_parts()) != 1:
                score -= 1000
            if format.container == "mkv":
                score += 10
            if score > best_score:
                best_score = score
                best_format = format

        if not best_format:
            QtWidgets.QMessageBox.critical(None, "Cannot play Video", "no suitable format found")
            return

        # Check if we need to transcode
        ts = None
        if best_format.video_height > 750 or self.force_transcode:
            ts = TranscodeSession.from_library(video,
                                               protocol="http",
                                               videoResolution="720",
                                               fastSeek=1,
                                               directPlay=0,
                                               )
            stream_url = ts.url
            logging.info("New transcode session: %s" % ts.uuid)
        else:
            stream_url = self.conn.get_url(best_format.get_parts()[0].path)

        proc = QtCore.QProcess(self)
        proc.setProgram("/usr/bin/vlc")
        proc.setArguments([stream_url, "vlc://quit"])

        self.statusBar().showMessage("Watching '%s'%s" % (video.title, " (transcode)" if ts else ""))

        start_time = time.time()

        def onFinished(code, status):
            if time.time() - start_time >= video.duration / 2000:
                video.mark_watched()
            if ts is not None:
                ts.stop()
            self.statusBar().showMessage("Finished watching '%s'" % video.title)

        proc.finished.connect(onFinished)

        proc.start()


class CPGuiClient(Client):
    Device = None
    DeviceName = None
    ClientIdentifier = None

    @staticmethod
    def get_or_set(settings, key, value, default=None):
        if value is None:
            value = settings.value(key, None)
            if value is not None or default is None:
                return value
            else:
                value = default
        settings.setValue(key, value)
        return value

    def __init__(self, client_id=None, device=None, device_name=None):
        settings = QtCore.QSettings()

        settings.beginGroup("Client")
        client_id = self.get_or_set(settings, "Client", client_id, str(uuid.uuid4()))
        device = self.get_or_set(settings, "Device", device, "VLC")
        device_name = self.get_or_set(settings, "DeviceName", device_name, "VLC Media Player")
        settings.endGroup()

        del settings

        super().__init__(client_id)

        self.ClientIdentifier = client_id
        self.Device = device
        self.DeviceName = device_name


# noinspection PyArgumentList
if __name__ == "__main__":
    # Setup application
    logging.basicConfig(level=logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationDisplayName("comPlex GUI")
    app.setOrganizationName("Orochimarufan")
    app.setApplicationName("comPlex")
    app.setApplicationVersion(__version__)

    # Read settings
    settings = QtCore.QSettings()

    settings.beginGroup("Server")
    server_host = settings.value("Host", None)
    server_port = settings.value("Port", 32400, type=int)

    if server_host is None:
        server_host, ok = QtWidgets.QInputDialog.getText(None, "comPlex server host",
                                                         "Please enter the Plex server to connect to")

        if not ok:
            logging.error("Host input dialog aborted.")
            sys.exit(1)

        if ":" in server_host:
            server_host, server_port = server_host.split(":", 1)
            server_port = int(server_port)

        settings.setValue("Host", server_host)
        settings.setValue("Port", server_port)

    settings.endGroup()

    settings.beginGroup("GUI")
    ChildItem.KeepImageInMemory = settings.value("KeepThumbnailsInMemory", False, type=bool)
    settings.endGroup()

    del settings

    # Connect to server
    conn = Connection(CPGuiClient(), host=server_host, port=server_port)
    conn.refresh()

    # Setup the cache
    CACHE_PATH = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.CacheLocation)

    logging.info("Cache at %s/%s", CACHE_PATH, conn.name)

    if not os.path.isdir(os.path.join(CACHE_PATH, conn.name)):
        os.makedirs(os.path.join(CACHE_PATH, conn.name))

    # Show window & run
    win = MainWindow(conn)

    win.show()
    sys.exit(app.exec())
