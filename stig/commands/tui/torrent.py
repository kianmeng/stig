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

"""Torrent commands for the TUI"""

from ...logging import make_logger
log = make_logger(__name__)

from collections import abc

from ..base import torrent as base
from . import mixin
from .. import ExpectedResource
from ...utils import strcrop
from . import make_tab_title


class AddTorrentsCmd(base.AddTorrentsCmdbase,
                     mixin.polling_frenzy, mixin.make_request):
    provides = {'tui'}


class ListTorrentsCmd(base.ListTorrentsCmdbase):
    provides = {'tui'}
    tui = ExpectedResource

    def make_tlist(self, filters, sort, columns):
        from ...tui.torrent.tlist import TorrentListWidget
        tlistw = TorrentListWidget(filters=filters, sort=sort, columns=columns)
        titlew = make_tab_title('T', tlistw.title,
                                'tabs.torrentlist.unfocused', 'tabs.torrentlist.focused')
        self.tui.tabs.load(titlew, tlistw)
        return True


class ListFilesCmd(base.ListFilesCmdbase,
                   mixin.make_request, mixin.select_torrents, mixin.select_files):
    provides = {'tui'}
    tui = ExpectedResource
    srvapi = ExpectedResource

    async def make_flist(self, tfilters, ffilters, columns):
        from ...tui.torrent.flist import FileListWidget
        flistw = FileListWidget(self.srvapi, tfilters, ffilters, columns)

        if isinstance(tfilters, abc.Sequence) and len(tfilters) == 1:
            # tfilters is a torrent ID - resolve it to a name for the title
            response = await self.srvapi.torrent.torrents(tfilters, keys=('name',))
            title = strcrop(response.torrents[0]['name'], 30, tail='…')
        else:
            if ffilters is None:
                title = str(tfilters)
            else:
                title = '%s files of %s torrents' % (ffilters, tfilters)
        titlew = make_tab_title('F', title,
                                'tabs.filelist.unfocused', 'tabs.filelist.focused')
        self.tui.tabs.load(titlew, flistw)
        return True


class PriorityCmd(base.PriorityCmdbase,
                  mixin.polling_frenzy, mixin.make_request, mixin.select_torrents, mixin.select_files):
    provides = {'tui'}


class RemoveTorrentsCmd(base.RemoveTorrentsCmdbase,
                        mixin.polling_frenzy, mixin.make_request, mixin.select_torrents):
    provides = {'tui'}


class StartTorrentsCmd(base.StartTorrentsCmdbase,
                       mixin.polling_frenzy, mixin.make_request, mixin.select_torrents):
    provides = {'tui'}


class StopTorrentsCmd(base.StopTorrentsCmdbase,
                      mixin.polling_frenzy, mixin.make_request, mixin.select_torrents):
    provides = {'tui'}


class VerifyTorrentsCmd(base.VerifyTorrentsCmdbase,
                        mixin.make_request, mixin.select_torrents):
    provides = {'tui'}
