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

from ...logging import make_logger
log = make_logger(__name__)

import urwid
import urwidtrees
from collections import abc
import builtins

from .flist_columns import TUICOLUMNS
from . import (ItemWidgetBase, ListWidgetBase, stringify_torrent_filter)


from ...views.filelist import (create_directory_data, create_directory_name)
from urwidtrees.decoration import ArrowTree
class FileTreeDecorator(ArrowTree):
    """urwidtrees decorator for TorrentFiles and TorrentFileTrees"""

    def __init__(self, torrents, keymap, table, ffilter):
        self._filewidgetcls = keymap.wrap(FileItemWidget, context='file')
        self._table = table
        self._ffilter = ffilter
        self._widgets = {}
        self._filtered_counts = {}
        forest = self._create_file_forest(torrents)
        super().__init__(forest, indent=2)

    def _file_is_filtered(self, tfile):
        if self._ffilter is None:
            return False  # No filter specified
        elif isinstance(self._ffilter, (abc.Sequence, abc.Set)):
            # ffilter is a collection of file IDs
            return not tfile['id'] in self._ffilter
        else:
            # ffilter is a TorrentFileFilter instance
            return not self._ffilter.match(tfile)

    def _create_file_forest(self, torrents):
        # Create a list of nested trees in SimpleTree format.  But the leaves
        # are mappings instead of widgets.  Each mapping contains the
        # information that the `decorate` method needs to create a widget.

        def create_tree(node, content):
            if content.nodetype == 'leaf':
                # Torrent has a single file and no directories
                if not self._file_is_filtered(content):
                    return (content, None)
                else:
                    return None

            elif content.nodetype == 'parent':
                # Torrent has at least one directory
                tree = []
                filtered_count = 0
                for k,v in sorted(content.items(), key=lambda pair: pair[0].lower()):
                    if v.nodetype == 'leaf':
                        if not self._file_is_filtered(v):
                            tree.append((v, None))
                            nonlocal fcount
                            fcount += 1
                        else:
                            filtered_count += 1
                    elif v.nodetype == 'parent':
                        dirnode = create_directory_data(name=k, tree=v)
                        tree.append(create_tree(dirnode, v))

                node_id = (node['tid'], node['id'])
                self._filtered_counts[node_id] = filtered_count
                node['name'] = create_directory_name(node['name'], filtered_count)
                return (node, tree or None)

        fcount = 0
        forest = []  # Multiple trees as siblings
        for t in sorted(torrents, key=lambda t: t['name'].lower()):
            filetree = t['files']
            # This works because t['files'] always has 1 item: the torrent's name
            rootnodename = next(iter(filetree.keys()))
            rootnode = create_directory_data(rootnodename, tree=filetree)
            tree = create_tree(rootnode, filetree[rootnodename])
            if tree is not None:
                forest.append(tree)
        self.filecount = fcount
        return forest

    def decorate(self, pos, data, is_first=True):
        # We can use the tree position as table ID
        self._table.register(pos)
        row = self._table.get_row(pos)

        # We use parent's decorate() method to give the name column a tree
        # structure.  But we also need the original update() method so we can
        # apply new data to the widget.  This is dirty but it works.
        update_method = row.name.update
        decowidget = super().decorate(pos, row.name, is_first=is_first)
        decowidget.update = update_method
        row.replace('name', decowidget)

        # Wrap the whole row in a FileItemWidget with keymapping.  This also
        # applies all the other values besides the name (size, progress, etc).
        file_widget = self._filewidgetcls(data, row)
        node_id = (data['tid'], data['id'])
        self._widgets[node_id] = file_widget
        return file_widget

    def update(self, torrents):
        widgets = self._widgets
        for t in torrents:
            tid = t['id']

            # Update file nodes
            for f in t['files'].files:
                fid = f['id']
                node_id = (tid, fid)
                if node_id in widgets:
                    widgets[node_id].update(f)

            # Update directory nodes
            for name,content in t['files'].directories:
                fids = frozenset(f['id'] for f in content.files)
                node_id = (tid, fids)
                if node_id in widgets:
                    filtered_count = self._filtered_counts[node_id]
                    data = create_directory_data(name, tree=content,
                                                 filtered_count=filtered_count)
                    widgets[node_id].update(data)

    @property
    def widgets(self):
        """Yield all file and directory widgets in this tree"""
        yield from self._widgets.values()



class FileItemWidget(ItemWidgetBase):
    palette_unfocused = 'filelist'
    palette_focused   = 'filelist.focused'
    columns_focus_map = {}
    for col in TUICOLUMNS.values():
        columns_focus_map.update(col.style.focus_map)


    @property
    def torrent_id(self):
        return self._item['tid']

    @property
    def file_id(self):
        return self._item['id']

    @property
    def nodetype(self):
        """'parent' or 'leaf'"""
        return self._item.nodetype


class FileListWidget(ListWidgetBase):
    tuicolumns      = TUICOLUMNS
    ListItemClass   = FileItemWidget
    keymap_context  = 'file'
    palette_name    = 'filelist'
    focusable_items = True

    def __init__(self, srvapi, keymap, tfilter, ffilter, columns=None, title=None):
        super().__init__(srvapi, keymap, columns=columns, title=title)
        self._tfilter = tfilter
        self._ffilter = ffilter
        self._initialized = False

        self._poller = self._srvapi.create_poller(
            self._srvapi.torrent.torrents, tfilter, keys=('files', 'name'),
            autoconnect=False
        )
        self._poller.on_response(self._handle_files)

    def _handle_files(self, response):
        if response is None or not response.torrents:
            self.clear()
        else:
            if self._initialized:
                self._update_listitems(response.torrents)
            else:
                self._init_listitems(response.torrents)
        self._invalidate()

    def _init_listitems(self, torrents):
        # Auto-generate title from our filters
        if self._title_name is None:
            self._title_name = stringify_torrent_filter(self._tfilter, torrents)
            if self._ffilter:
                self._title_name += ' %s' % self._ffilter

        self.clear()
        if torrents:
            self._filetree = FileTreeDecorator(torrents, self._keymap,
                                               self._table, self._ffilter)
            self._listbox.body = urwidtrees.widgets.TreeListWalker(self._filetree)
            self._listbox._invalidate()
            self._initialized = True

    def _update_listitems(self, torrents=()):
        if torrents:
            self._filetree.update(torrents)

    def clear(self):
        # We can't call super().clear() because it runs the more efficient
        # `self._listbox.body[:] = ()`
        # That doesn't work here because urwidtrees.TreeListWalker doesn't
        # support item assignment.
        self._listbox.body = urwid.SimpleListWalker([])
        self._listbox._invalidate()
        self._initialized = False
        self._table.clear()
        self._marked.clear()


    @property
    def count(self):
        return self._filetree.filecount if hasattr(self, '_filetree') else 0

    @property
    def focus_position(self):
        positions = tuple(self._filetree.positions())
        return positions.index(self._listbox.focus_position)

    @focus_position.setter
    def focus_position(self, focus_position):
        positions = tuple(self._filetree.positions())
        i = min(focus_position, len(positions)-1)
        try:
            self._listbox.focus_position = positions[i]
        except KeyError:
            pass

    @property
    def focused_file_ids(self):
        """File IDs of the focused files in a tuple"""
        focused = self.focused_widget
        if focused is not None:
            # The focused widget in the list can be a file or a directory.  If
            # it's a directory, the 'file_id' property returns the IDs of all
            # the contained files recursively.
            fid = focused.file_id
            return tuple(fid) if isinstance(fid, (abc.Sequence, abc.Set)) else (fid,)


    def all_children(self, pos):
        """Yield (position, widget) tuples of all sub-nodes (leaves and parents)"""
        ft = self._filetree
        lb = self._listbox
        def recurse(subpos):
            widget = lb.body[subpos]
            if ft.is_leaf(subpos):
                yield (subpos, widget)
            else:
                # Yield sub-parent nodes, but not the starting node that was
                # passed to us
                if subpos != pos:
                    yield (subpos, widget)

                new_subpos = ft.first_child_position(subpos)
                while new_subpos is not None:
                    yield from recurse(new_subpos)
                    new_subpos = ft.next_sibling_position(new_subpos)

        yield from recurse(pos)

    def _set_mark(self, mark, toggle=False, all=False):
        if toggle:
            focused = self.focused_widget
            if focused is not None:
                mark = not focused.is_marked

        def get_widget(pos):
            return self._listbox.body[pos]

        def mark_leaves(pos, mark):
            get_widget(pos).is_marked = mark

            for subpos,widget in self.all_children(pos):
                if widget.nodetype == 'leaf':
                    widget.is_marked = mark
                    if mark:
                        self._marked.add(widget)
                    else:
                        self._marked.discard(widget)

                elif widget.nodetype == 'parent':
                    if pos != subpos:  # Avoid infinite recursion
                        mark_leaves(subpos, mark)

        if all:
            # Top ancestor node positions are (0,), (1,), (3,) etc
            for pos in self._filetree.positions():
                if len(pos) == 1:
                    mark_leaves(pos, mark)
        else:
            mark_leaves(self._listbox.focus_position, mark)
        assert builtins.all(m.nodetype == 'leaf' for m in self._marked)

        # A parent node is marked only if all its children are marked.  To check
        # that, we walk through every ancestor up to the top and check all its
        # children.  There is no need to check the children of other parent
        # nodes (uncles, great uncles, etc) because they should already be
        # marked properly from previous runs.

        def all_children_marked(pos):
            marked = True
            childpos = self._filetree.first_child_position(pos)
            while childpos is not None:
                marked = marked and get_widget(childpos).is_marked
                childpos = self._filetree.next_sibling_position(childpos)
            return marked

        parpos = self._filetree.parent_position(self._listbox.focus_position)
        while parpos is not None:
            parwidget = get_widget(parpos)
            parwidget.is_marked = all_children_marked(parpos)
            parpos = self._filetree.parent_position(parpos)

    def refresh_marks(self):
        for widget in self._filetree.widgets:
            widget.is_marked = widget.is_marked
