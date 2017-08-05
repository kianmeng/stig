# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details
# http://www.gnu.org/licenses/gpl-3.0.txt

import urwid

from .. import main as tui

from ..scroll import ScrollBar
from ..table import Table
from .plist_columns import TUICOLUMNS
from . import make_ItemWidget_class


PeerItemWidget = make_ItemWidget_class('Peer', TUICOLUMNS, unfocused='peerlist')

class PeerListWidget(urwid.WidgetWrap):
    def __init__(self, srvapi, tfilter, pfilter, columns, sort=None, title=None):
        self._sort = sort
        self._sort_orig = sort
        self._tfilter = tfilter
        self._pfilter = pfilter

        # Create peer filter generator
        if pfilter is not None:
            def filter_peers(peers):
                yield from pfilter.apply(peers)
        else:
            def filter_peers(peers):
                yield from peers
        self._maybe_filter_peers = filter_peers

        self._title = title
        self.title_updater = None

        self._peers = ()
        self._initialized = False

        self._table = Table(**TUICOLUMNS)
        self._table.columns = columns

        self._listbox = tui.keymap.wrap(urwid.ListBox, context='peerlist')(urwid.SimpleListWalker([]))
        listbox_sb = urwid.AttrMap(
            ScrollBar(urwid.AttrMap(self._listbox, 'peerlist')),
            'scrollbar'
        )
        pile = urwid.Pile([
            ('pack', urwid.AttrMap(self._table.headers, 'peerlist.header')),
            listbox_sb
        ])
        super().__init__(pile)

        self._poller = srvapi.create_poller(
            srvapi.torrent.torrents, tfilter, keys=('peers', 'name', 'id'))
        self._poller.on_response(self._handle_response)

    def _handle_response(self, response):
        if response is None or not response.torrents:
            self.clear()
        else:
            def peers_combined(torrents):
                for t in torrents:
                    yield from self._maybe_filter_peers(t['peers'])
            self._peers = {p['id']:p for p in peers_combined(response.torrents)}

        if self.title_updater is not None:
            # First argument can be cropped if too long, second argument is fixed
            self.title_updater(self.title, ' [%d]' % self.count)

        self._invalidate()

    def render(self, size, focus=False):
        if self._peers is not None:
            self._update_listitems()
            self._peers = None
        return super().render(size, focus)

    def _update_listitems(self):
        pdict = self._peers
        walker = self._listbox.body
        dead_pws = []
        for pw in walker:  # pw = PeerItemWidget
            pid = pw.id
            try:
                # Update existing peer widget with new data
                pw.update(pdict[pid])
                del pdict[pid]
            except KeyError:
                # Peer no longer exists
                dead_pws.append(pw)

        # Remove list items
        for pw in dead_pws:
            walker.remove(pw)

        # Any peers that haven't been used to update an existing peer widget are new
        for pid in pdict:
            self._table.register(pid)
            row = self._table.get_row(pid)
            walker.append(PeerItemWidget(pdict[pid], row))

        # Sort peers
        if self._sort is not None:
            self._sort.apply(walker,
                            item_getter=lambda pw: pw.item,
                            inplace=True)

    def clear(self):
        """Remove all list items"""
        self._table.clear()
        self._listbox.body[:] = []
        self._listbox._invalidate()

    @property
    def sort(self):
        """TorrentPeerSorter object (set to `None` to restore original sort order)"""
        return self._sort

    @sort.setter
    def sort(self, sort):
        if sort == 'RESET':
            self._sort = self._sort_orig
        else:
            self._sort = sort
        self._poller.poll()

    @property
    def title(self):
        # Create the fixed part of the title (everything minus the number of peers listed)
        # If title is not given, create one from filter and sort order
        if self._title is None:
            # self._tfilter is either None or an actual TorrentFilter instance
            title = str(self._tfilter or 'all')
            if self._pfilter:
                title += ' %s' % self._pfilter
        else:
            title = self._title

        if self._sort is not None:
            sortstr = str(self._sort)
            if sortstr is not self._sort.DEFAULT_SORT:
                title += ' {%s}' % sortstr
        return title

    @property
    def count(self):
        """Number of listed peers"""
        # If this method was called before rendering, the contents of the
        # listbox widget are inaccurate and we have to use self._peers.  But
        # if we're called after rendering, self._peers is reset to None.
        if self._peers is not None:
            return len(self._peers)
        else:
            return len(self._listbox.body)
