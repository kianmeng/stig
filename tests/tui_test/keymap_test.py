import unittest
from stig.tui.keymap import (Key, KeyChain, KeyMap)
from urwid import (Text, ListBox, SimpleFocusListWalker, Pile)
import stig.tui.urwidpatches

from .resources_tui import get_canvas_text

import logging
log = logging.getLogger(__name__)


class TestKey(unittest.TestCase):
    def test_compare_Key_with_Key(self):
        self.assertEqual(Key('alt-l'), Key('Alt-l'))
        self.assertEqual(Key('alt-l'), Key('meta-l'))
        self.assertEqual(Key('alt-l'), Key('Meta-l'))
        self.assertEqual(Key('alt-l'), Key('<alt-l>'))
        self.assertNotEqual(Key('alt-l'), Key('alt-L'))

        self.assertEqual(Key('ctrl-e'), Key('Ctrl-e'))
        self.assertEqual(Key('ctrl-e'), Key('<ctrl-e>'))
        self.assertEqual(Key('ctrl-e'), Key('CTRL-e'))
        self.assertEqual(Key('ctrl-e'), Key('ctrl-E'))

        self.assertEqual(Key('space'), Key(' '))
        self.assertEqual(Key('escape'), Key('esc'))
        self.assertEqual(Key('home'), Key('pos1'))
        self.assertEqual(Key('delete'), Key('del'))
        self.assertEqual(Key('insert'), Key('ins'))

        self.assertEqual(Key('enter'), Key('return'))
        self.assertEqual(Key('enter'), Key('\n'))
        self.assertEqual(Key('alt-enter'), Key('meta-\n'))

        self.assertEqual(Key('alt-insert'), Key('meta ins'))
        self.assertEqual(Key('alt-del'), Key('meta delete'))
        self.assertEqual(Key('shift-ctrl-enter'), Key('shift-Ctrl-RETURN'))
        self.assertEqual(Key('alt-space'), Key('meta  '))
        self.assertEqual(Key('alt-pgup'), Key('meta page up'))

    def test_compare_Key_with_str(self):
        self.assertEqual(Key('enter'), '\n')
        self.assertEqual(Key('enter'), 'return')
        self.assertEqual(Key('pgdn'), 'page down')
        self.assertEqual(Key('pgup'), 'page up')
        self.assertEqual(Key('space'), ' ')
        self.assertEqual(Key('ins'), 'insert')
        self.assertEqual(Key('insert'), 'ins')

    def test_convert_shift_modifier(self):
        self.assertEqual(Key('shift-E'), Key('E'))
        self.assertEqual(Key('shift-e'), Key('E'))
        self.assertEqual(Key('shift-ö'), Key('Ö'))
        self.assertEqual(Key('shift-alt-ö'), Key('alt-Ö'))
        self.assertEqual(Key('ctrl-shift-alt-ö'), Key('ctrl-alt-Ö'))

    def test_invalid_modifier(self):
        with self.assertRaises(ValueError) as cm:
            Key('shit-e')
        self.assertIn('Invalid modifier', str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            Key('alt-')
        self.assertIn('Missing key', str(cm.exception))

    def test_invalid_key(self):
        with self.assertRaises(ValueError) as cm:
            Key('hello')
        self.assertIn('Unknown key', str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            Key('alt-hello')
        self.assertIn('Unknown key', str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            Key('')
        self.assertIn('No key', str(cm.exception))


class FakeAction():
    def __init__(self, action=None):
        self.callnum = 0
        self.action = action
    def run(self, widget):
        self.callnum += 1
        if self.action is not None:
            return self.action()

class TestKeyMapped(unittest.TestCase):
    def setUp(self):
        self.keymap = KeyMap()

    def mk_widget(self, subcls, *args, context=None, callback=None, **kwargs):
        cls = self.keymap.wrap(subcls, context=context, callback=callback)
        return cls(*args, **kwargs)

    def assert_lines(self, widget, size, exp_lines, exp_focus_pos=None):
        canv = widget.render(size, focus=True)
        content = tuple(get_canvas_text(row) for row in canv.content())
        self.assertEqual(content, tuple(exp_lines))
        if exp_focus_pos is not None:
            self.assertEqual(widget.focus_position, exp_focus_pos)

    def test_hardcoded_keys_keep_working(self):
        list_contents = [Text(str(i)) for i in range(1, 10)]
        widget = self.mk_widget(ListBox, SimpleFocusListWalker(list_contents),
                                context='foocon')
        size = (3, 3)
        self.assert_lines(widget, size, exp_lines=('1  ', '2  ', '3  '))
        widget.keypress(size, 'down')
        self.assert_lines(widget, size, exp_lines=('2  ', '3  ', '4  '))
        widget.keypress(size, 'page down')
        self.assert_lines(widget, size, exp_lines=('5  ', '6  ', '7  '))
        widget.keypress(size, 'up')
        self.assert_lines(widget, size, exp_lines=('4  ', '5  ', '6  '))
        widget.keypress(size, 'page up')
        self.assert_lines(widget, size, exp_lines=('1  ', '2  ', '3  '))

    def test_non_hardcoded_keys_are_evaluated(self):
        list_contents = [Text(str(i)) for i in range(1, 10)]
        widget = self.mk_widget(ListBox, SimpleFocusListWalker(list_contents),
                                context='foocon')
        action = FakeAction()
        self.keymap.bind('a', context='foocon', action=action.run)
        size = (3, 3)
        self.assert_lines(widget, size, exp_lines=('1  ', '2  ', '3  '))
        widget.keypress(size, 'a')
        self.assert_lines(widget, size, exp_lines=('1  ', '2  ', '3  '))
        self.assertEqual(action.callnum, 1)

    def test_evaluated_keys_are_offered_to_parent_again(self):
        list_contents = [Text(str(i)) for i in range(1, 10)]
        widget = self.mk_widget(ListBox, SimpleFocusListWalker(list_contents),
                                context='foocon')
        self.keymap.bind('j', context='foocon', action=Key('down'))
        size = (3, 3)
        self.assert_lines(widget, size, exp_lines=('1  ', '2  ', '3  '))
        widget.keypress(size, 'j')
        self.assert_lines(widget, size, exp_lines=('2  ', '3  ', '4  '))

    def test_evaluated_key_does_not_replace_original_key(self):
        # Create a list of widgets that translate 'j' to 'down' in their
        # keypress() methods.
        lst_contents = [self.mk_widget(Text, str(i), context='barcon')
                        for i in range(1, 10)]
        self.keymap.bind('j', context='barcon', action=Key('down'))

        # Create ListBox with separate key context.  If the ListBox gets to
        # handle 'j', it just checks a mark we can look for.
        lst_widget = self.mk_widget(ListBox, SimpleFocusListWalker(lst_contents), context='foocon')
        lst_got_j = FakeAction()
        self.keymap.bind('j', context='foocon', action=lst_got_j.run)

        # Make sure everything works regularly
        size = (3, 3)
        self.assert_lines(lst_widget, size, exp_lines=('1  ', '2  ', '3  '), exp_focus_pos=0)
        lst_widget.keypress(size, 'down')
        self.assert_lines(lst_widget, size, exp_lines=('1  ', '2  ', '3  '), exp_focus_pos=1)

        # Do the actual test: Pressing 'j' should pass 'j' to the focused list
        # item, which evaluates it to 'down'.  But 'down' must NOT be used to
        # move focus down.
        lst_widget.keypress(size, 'j')
        self.assert_lines(lst_widget, size, exp_lines=('1  ', '2  ', '3  '), exp_focus_pos=1)
        self.assertEqual(lst_got_j.callnum, 1)


class TestKeyMap(unittest.TestCase):
    def setUp(self):
        self.km = KeyMap()

    def test_circular_bind_detection(self):
        with self.assertRaises(ValueError) as cm:
            self.km.bind(key='a', action=self.km.mkkey('a'))
        self.assertIn('Circular', str(cm.exception))
        self.assertIn('<a>', str(cm.exception))

    def test_unbind(self):
        self.km.bind(key='a', action='foo')
        self.assertIn(Key('a'), self.km.keys())
        self.km.unbind(key='a')
        self.assertNotIn(Key('a'), self.km.keys())

        self.km.bind(key='b', action='foo')
        with self.assertRaises(ValueError):
            self.km.unbind(key='c')

        self.km.bind(key='d', action='foo')
        with self.assertRaises(ValueError):
            self.km.unbind(key='d', context='bar')

    def test_mkkey(self):
        self.assertEqual(self.km.mkkey(Key('x')), Key('x'))
        self.assertEqual(self.km.mkkey(KeyChain('1', '2', '3')),
                         KeyChain('1', '2', '3'))

        self.assertEqual(self.km.mkkey('x'), Key('x'))
        self.assertEqual(self.km.mkkey('x y z'), KeyChain('x', 'y', 'z'))
        self.assertEqual(self.km.mkkey('x+y+z'), KeyChain('x', 'y', 'z'))
        self.assertEqual(self.km.mkkey('x +'), KeyChain('x', '+'))
        self.assertEqual(self.km.mkkey('+ x'), KeyChain('+', 'x'))
        self.assertEqual(self.km.mkkey('x y +'), KeyChain('x', 'y', '+'))
        self.assertEqual(self.km.mkkey('+ y z'), KeyChain('+', 'y', 'z'))
        self.assertEqual(self.km.mkkey('+ + +'), KeyChain('+', '+', '+'))

    def test_key_translation(self):
        self.km.bind(key='a',
                     action=lambda widget: widget.set_text('Key pressed: a'))
        self.km.bind(key='b', action=Key('a'))
        widget = self.km.wrap(Text)('Test Text')
        widget.keypress((80,), 'b')
        self.assertEqual(widget.text, 'Key pressed: a')

    def test_action_is_callback(self):
        self.km.bind(key='a',
                     action=lambda widget: widget.set_text('foo'))
        widget = self.km.wrap(Text)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'foo')

    def test_widget_callback(self):
        def cb(action, widget):
            widget.set_text(action)

        self.km.bind(key='a', action='foo')
        widget = self.km.wrap(Text, callback=cb)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'foo')

    def test_default_callback(self):
        def cb(action, widget):
            widget.set_text(action)

        self.km = KeyMap(callback=cb)
        self.km.bind(key='a', action='foo')
        widget = self.km.wrap(Text)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'foo')

    def test_widget_callback_overrides_default_callback(self):
        def default_cb(action, widget):
            widget.set_text(action)

        def widget_cb(action, widget):
            widget.set_text(action.upper())

        self.km = KeyMap(callback=default_cb)
        self.km.bind(key='a', action='foo')
        widget = self.km.wrap(Text, callback=widget_cb)('Test Text')
        widget.keypress((80,), 'a')
        self.assertEqual(widget.text, 'FOO')


class TestKeyChain(unittest.TestCase):
    def test_advance(self):
        kc = KeyChain('a', 'b', 'c')
        for _ in range(10):
            self.assertEqual(kc.given, ())
            kc.advance()
            self.assertEqual(kc.given, ('a',))
            kc.advance()
            self.assertEqual(kc.given, ('a', 'b'))
            kc.advance()
            self.assertEqual(kc.given, ('a', 'b', 'c'))
            kc.advance()

    def test_reduce(self):
        kc = KeyChain('a', 'b', 'c')
        for _ in range(10):
            self.assertEqual(kc.given, ())
            kc.advance()
            self.assertEqual(kc.given, ('a',))
            kc.advance()
            self.assertEqual(kc.given, ('a', 'b'))
            kc.reduce()
            self.assertEqual(kc.given, ('a',))
            kc.reduce()
            self.assertEqual(kc.given, ())
            kc.reduce()
            self.assertEqual(kc.given, ())

    def test_reset(self):
        kc = KeyChain('a', 'b', 'c')
        for i in range(10):
            for _ in range(i): kc.advance()
            kc.reset()
            self.assertEqual(kc.given, ())

    def test_next_key(self):
        kc = KeyChain('a', 'b', 'c')
        for i in range(10):
            self.assertEqual(kc.next_key, 'a')
            kc.advance()
            self.assertEqual(kc.next_key, 'b')
            kc.advance()
            self.assertEqual(kc.next_key, 'c')
            kc.advance()
            self.assertEqual(kc.next_key, None)  # chain is complete
            kc.advance()  # same as reset() if complete

    def test_startswith(self):
        kc = KeyChain('a', 'b', 'c')
        self.assertEqual(kc.startswith(('a',)), True)
        self.assertEqual(kc.startswith(('a', 'b')), True)
        self.assertEqual(kc.startswith(('a', 'b', 'c')), True)
        self.assertEqual(kc.startswith(('a', 'b', 'c', 'x')), False)
        self.assertEqual(kc.startswith(('a', 'b', 'x')), False)
        self.assertEqual(kc.startswith(('a', 'x')), False)
        self.assertEqual(kc.startswith(('x')), False)
        self.assertEqual(kc.startswith(()), True)

    def test_is_complete(self):
        kc = KeyChain('a', 'b', 'c')
        for i in range(10):
            self.assertEqual(kc.is_complete, False)
            kc.advance()
            self.assertEqual(kc.is_complete, False)
            kc.advance()
            self.assertEqual(kc.is_complete, False)
            kc.advance()
            self.assertEqual(kc.is_complete, True)
            kc.reset()

    def test_feed_with_correct_chain(self):
        kc = KeyChain('a', 'b', 'c')
        self.assertEqual(kc.feed('a'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('b'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('c'), KeyChain.COMPLETED)

    def test_feed_with_wrong_chain(self):
        kc = KeyChain('a', 'b', 'c')
        self.assertEqual(kc.feed('x'), KeyChain.REJECTED)

        self.assertEqual(kc.feed('a'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('x'), KeyChain.ABORTED)

        self.assertEqual(kc.feed('a'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('b'), KeyChain.ADVANCED)
        self.assertEqual(kc.feed('x'), KeyChain.ABORTED)


class TestKeyMap_with_keychains(unittest.TestCase):
    def setUp(self):
        self.km = KeyMap(callback=self.handle_action)
        self.widget = self.km.wrap(Text)('Original Text')
        self.km.on_keychain(self.handle_keychain_changed)
        self._action_counter = 0

    def handle_action(self, action, widget):
        self._action_counter += 1
        widget.set_text('%s%d' % (str(action), self._action_counter))

    def handle_keychain_changed(self, active_keychains):
        self.active_keychains = set(active_keychains)

    def assert_status(self, active_keychains=(), keys_given=(), widget_text=None):
        self.assertEqual(self.active_keychains, set(active_keychains))
        for keychain,action in self.active_keychains:
            self.assertEqual(keychain.given, keys_given)
        self.assertEqual(self.widget.text, widget_text)


    def test_unbind(self):
        kc = '1 2 3'
        for keys in ('1', '1 2', '1 2 3'):
            self.km.bind(kc, 'foo')
            self.assertIn(KeyChain('1', '2', '3'), self.km.keys())
            self.km.unbind(keys)
            self.assertNotIn(KeyChain('1', '2', '3'), self.km.keys())

        for keys in ('1 3', '1 2 4', '1 2 3 4', '2', '3', '2 1', '3 2 1'):
            self.km.bind(kc, 'foo')
            self.assertIn(KeyChain('1', '2', '3'), self.km.keys())
            with self.assertRaises(ValueError) as cm:
                self.km.unbind(keys)
            self.assertIn('Key not mapped', str(cm.exception))
            self.assertIn('default context', str(cm.exception))
            self.assertIn(str(self.km.mkkey(keys)), str(cm.exception))

    def test_correct_chain(self):
        self.km.bind('1 2 3', 'foo')

        self.widget.keypress((80,), '1')
        self.assert_status(keys_given=('1',),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', '3'), 'foo'),))

        self.widget.keypress((80,), '2')
        self.assert_status(keys_given=('1', '2'),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', '3'), 'foo'),))

        self.widget.keypress((80,), '3')
        self.assert_status(keys_given=(),
                           widget_text='foo1',
                           active_keychains=())

    def test_abort_chain_with_unbound_key(self):
        self.km.bind('1 2 3', 'foo')

        self.widget.keypress((80,), '1')
        self.assert_status(keys_given=('1',),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', '3'), 'foo'),))

        self.widget.keypress((80,), 'x')
        self.assert_status(keys_given=(),
                           widget_text='Original Text',
                           active_keychains=())

    def test_abort_chain_with_bound_key(self):
        self.km.bind('1 2 3', 'foo')
        self.km.bind('x', 'bar')

        self.widget.keypress((80,), '1')
        self.assert_status(keys_given=('1',),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', '3'), 'foo'),))

        # Abort the started chain
        self.widget.keypress((80,), 'x')
        self.assert_status(keys_given=(),
                           widget_text='Original Text',
                           active_keychains=())

        # Regular single-key evaluation works again
        self.widget.keypress((80,), 'x')
        self.assert_status(keys_given=(),
                           widget_text='bar1',
                           active_keychains=())

    def test_abort_chain_with_builtin_key(self):
        self.km.bind('1 2 3', 'foo')

        self.widget.keypress((80,), '1')
        self.assert_status(keys_given=('1',),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', '3'), 'foo'),))

        # Abort the started chain
        self.widget.keypress((80,), 'down')
        self.assert_status(keys_given=(),
                           widget_text='Original Text',
                           active_keychains=())

    def test_competing_chains(self):
        self.km.bind('1 2 a', 'foo')
        self.km.bind('1 2 b', 'bar')

        self.widget.keypress((80,), '1')
        self.assert_status(keys_given=('1',),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', 'a'), 'foo'),
                                             (('1', '2', 'b'), 'bar')))

        self.widget.keypress((80,), '2')
        self.assert_status(keys_given=('1', '2'),
                           widget_text='Original Text',
                           active_keychains=((('1', '2', 'a'), 'foo'),
                                             (('1', '2', 'b'), 'bar')))

        self.widget.keypress((80,), 'a')
        self.assert_status(keys_given=(),
                           widget_text='foo1',
                           active_keychains=())

        self.widget.keypress((80,), '1')
        self.assert_status(keys_given=('1',),
                           widget_text='foo1',
                           active_keychains=((('1', '2', 'a'), 'foo'),
                                             (('1', '2', 'b'), 'bar')))

        self.widget.keypress((80,), '2')
        self.assert_status(keys_given=('1', '2'),
                           widget_text='foo1',
                           active_keychains=((('1', '2', 'a'), 'foo'),
                                             (('1', '2', 'b'), 'bar')))

        self.widget.keypress((80,), 'b')
        self.assert_status(keys_given=(),
                           widget_text='bar2',
                           active_keychains=())


class TestKeyMap_with_nested_widgets(unittest.TestCase):
    def setUp(self):
        self.km = KeyMap(callback=self.handle_action)
        self.km.on_keychain(self.handle_keychain_changed)
        self.last_action = None
        self.action_widget = None
        self.action_counter = 0
        self.active_keychains = set()

        # Create a Pile of two ListBoxes with some Text items
        def mk_item(i, context):
            return self.km.wrap(Text, context=context)('%s: %s' % (context, i))
        self.listw1 = self.km.wrap(ListBox, context='list1')(
            SimpleFocusListWalker([mk_item(i, context='item1')
                                   for i in range(1, 10)])
        )
        self.listw2 = self.km.wrap(ListBox, context='list2')(
            SimpleFocusListWalker([mk_item(i, context='item2')
                                   for i in range(100, 1000, 100)])
        )
        self.mainw = self.km.wrap(Pile, context='main')([self.listw1, self.listw2])

        self.km.bind('A',     'A in main',   context='main')
        self.km.bind('B',     'B in main',   context='main')
        self.km.bind('1 2 A', '12A in main', context='main')
        self.km.bind('1 2 B', '12B in main', context='main')

        self.km.bind('C',     'C in list1',   context='list1')
        self.km.bind('D',     'D in list1',   context='list1')
        self.km.bind('2 3 A', '23A in list1', context='list1')
        self.km.bind('2 3 B', '23B in list1', context='list1')

        self.km.bind('C',     'C in list2',   context='list2')
        self.km.bind('D',     'D in list2',   context='list2')
        self.km.bind('2 3 A', '23A in list2', context='list2')
        self.km.bind('2 3 B', '23B in list2', context='list2')

        self.km.bind('E',     'E in item1',   context='item1')
        self.km.bind('F',     'F in item1',   context='item1')
        self.km.bind('3 4 A', '34A in item1', context='item1')
        self.km.bind('3 4 B', '34B in item1', context='item1')

        self.km.bind('E',     'E in item2',   context='item2')
        self.km.bind('F',     'F in item2',   context='item2')
        self.km.bind('3 4 A', '34A in item2', context='item2')
        self.km.bind('3 4 B', '34B in item2', context='item2')


    def handle_action(self, action, widget):
        self.last_action = action
        self.action_counter += 1
        self.action_widget = widget

    def handle_keychain_changed(self, active_keychains):
        self.active_keychains = set(active_keychains)

    def press_key(self, key):
        self.mainw.keypress((80, 25), key)


    def assert_active_keychains(self, *active_keychains):
        self.assertEqual(self.active_keychains, set(active_keychains))

    def assert_current_keychain(self, *keys):
        # If there are no active keychains, we don't want this test to pass if
        # given keys are expected.
        ak = tuple(self.active_keychains)
        if len(keys) < 1:
            self.assertEqual(ak, ())
        else:
            for keychain,action in ak:
                self.assertEqual(keychain.given, keys)

    def assert_action(self, exp_action=None, exp_count=0, exp_widget=None):
        self.assertEqual(self.last_action, exp_action)
        self.assertEqual(self.action_counter, exp_count)
        self.assertEqual(self.action_widget, exp_widget)


    def test_mapped_singlekeys_in_main_context(self):
        self.press_key('A')
        self.assert_current_keychain()
        self.assert_action(exp_action='A in main', exp_count=1, exp_widget=self.mainw)
        self.assert_active_keychains()

        self.press_key('B')
        self.assert_current_keychain()
        self.assert_action(exp_action='B in main', exp_count=2, exp_widget=self.mainw)
        self.assert_active_keychains()

    def test_mapped_singlekeys_in_list_context(self):
        exp_count = 0
        for focuspos,context,listw in ((0, 'list1', self.listw1),
                                       (1, 'list2', self.listw2)):
            self.mainw.focus_position = focuspos
            exp_count += 1
            self.press_key('C')
            self.assert_current_keychain()
            self.assert_action(exp_action='C in %s' % context, exp_count=exp_count, exp_widget=listw)
            self.assert_active_keychains()
            exp_count += 1
            self.press_key('D')
            self.assert_current_keychain()
            self.assert_action(exp_action='D in %s' % context, exp_count=exp_count, exp_widget=listw)
            self.assert_active_keychains()

    def test_mapped_singlekeys_in_item_context(self):
        exp_count = 0
        for focuspos,context,listw in ((0, 'item1', self.listw1),
                                       (1, 'item2', self.listw2)):
            self.mainw.focus_position = focuspos
            exp_count += 1
            self.press_key('E')
            self.assert_current_keychain()
            self.assert_action(exp_action='E in %s' % context, exp_count=exp_count, exp_widget=listw.focus)
            self.assert_active_keychains()
            exp_count += 1
            self.press_key('F')
            self.assert_current_keychain()
            self.assert_action(exp_action='F in %s' % context, exp_count=exp_count, exp_widget=listw.focus)
            self.assert_active_keychains()

    def test_unmapped_singlekeys(self):
        self.press_key('Z')
        self.assert_current_keychain()
        self.assert_action(exp_action=None, exp_count=0, exp_widget=None)
        self.assert_active_keychains()


    def test_keychain_in_main_context(self):
        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('1')
            self.assert_current_keychain('1')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))
            self.press_key('2')
            self.assert_current_keychain('1', '2')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('A')
        self.assert_action(exp_action='12A in main', exp_count=1, exp_widget=self.mainw)
        self.assert_current_keychain()
        self.assert_active_keychains()

        start_keychain(exp_action='12A in main', exp_count=1, exp_widget=self.mainw)
        self.press_key('B')
        self.assert_action(exp_action='12B in main', exp_count=2, exp_widget=self.mainw)
        self.assert_current_keychain()
        self.assert_active_keychains()

    def test_keychain_in_list1_context(self):
        self.mainw.focus_position = 0

        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('2')
            self.assert_current_keychain('2')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('2', '3', 'A'), '23A in list1'),
                                         (('2', '3', 'B'), '23B in list1'))
            self.press_key('3')
            self.assert_current_keychain('2', '3')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('2', '3', 'A'), '23A in list1'),
                                         (('2', '3', 'B'), '23B in list1'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('A')
        self.assert_action(exp_action='23A in list1', exp_count=1, exp_widget=self.listw1)
        self.assert_current_keychain()
        self.assert_active_keychains()

        start_keychain(exp_action='23A in list1', exp_count=1, exp_widget=self.listw1)
        self.press_key('B')
        self.assert_action(exp_action='23B in list1', exp_count=2, exp_widget=self.listw1)
        self.assert_current_keychain()
        self.assert_active_keychains()

    def test_keychain_in_list2_context(self):
        self.mainw.focus_position = 1

        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('2')
            self.assert_current_keychain('2')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('2', '3', 'A'), '23A in list2'),
                                         (('2', '3', 'B'), '23B in list2'))
            self.press_key('3')
            self.assert_current_keychain('2', '3')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('2', '3', 'A'), '23A in list2'),
                                         (('2', '3', 'B'), '23B in list2'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('A')
        self.assert_action(exp_action='23A in list2', exp_count=1, exp_widget=self.listw2)
        self.assert_current_keychain()
        self.assert_active_keychains()

        start_keychain(exp_action='23A in list2', exp_count=1, exp_widget=self.listw2)
        self.press_key('B')
        self.assert_action(exp_action='23B in list2', exp_count=2, exp_widget=self.listw2)
        self.assert_current_keychain()
        self.assert_active_keychains()

    def test_keychain_in_item1_context(self):
        self.mainw.focus_position = 0

        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('3')
            self.assert_current_keychain('3')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('3', '4', 'A'), '34A in item1'),
                                         (('3', '4', 'B'), '34B in item1'))
            self.press_key('4')
            self.assert_current_keychain('3', '4')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('3', '4', 'A'), '34A in item1'),
                                         (('3', '4', 'B'), '34B in item1'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('A')
        self.assert_action(exp_action='34A in item1', exp_count=1, exp_widget=self.listw1.focus)
        self.assert_current_keychain()
        self.assert_active_keychains()

        start_keychain(exp_action='34A in item1', exp_count=1, exp_widget=self.listw1.focus)
        self.press_key('B')
        self.assert_action(exp_action='34B in item1', exp_count=2, exp_widget=self.listw1.focus)
        self.assert_current_keychain()
        self.assert_active_keychains()

    def test_keychain_in_item2_context(self):
        self.mainw.focus_position = 1

        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('3')
            self.assert_current_keychain('3')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('3', '4', 'A'), '34A in item2'),
                                         (('3', '4', 'B'), '34B in item2'))
            self.press_key('4')
            self.assert_current_keychain('3', '4')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('3', '4', 'A'), '34A in item2'),
                                         (('3', '4', 'B'), '34B in item2'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('A')
        self.assert_action(exp_action='34A in item2', exp_count=1, exp_widget=self.listw2.focus)
        self.assert_current_keychain()
        self.assert_active_keychains()

        start_keychain(exp_action='34A in item2', exp_count=1, exp_widget=self.listw2.focus)
        self.press_key('B')
        self.assert_action(exp_action='34B in item2', exp_count=2, exp_widget=self.listw2.focus)
        self.assert_current_keychain()
        self.assert_active_keychains()


    def test_abort_chain_with_builtin_key(self):
        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('1')
            self.assert_current_keychain('1')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))
            self.press_key('2')
            self.assert_current_keychain('1', '2')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('down')
        self.assert_action(exp_action=None, exp_count=0, exp_widget=None)
        self.assert_current_keychain()
        self.assert_active_keychains()

    def test_abort_chain_with_mapped_key(self):
        self.km.bind('x', 'x in main', context='main')

        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('1')
            self.assert_current_keychain('1')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))
            self.press_key('2')
            self.assert_current_keychain('1', '2')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('x')
        self.assert_action(exp_action=None, exp_count=0, exp_widget=None)
        self.assert_current_keychain()
        self.assert_active_keychains()

    def test_abort_chain_with_unmapped_key(self):
        def start_keychain(exp_action, exp_count, exp_widget):
            self.press_key('1')
            self.assert_current_keychain('1')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))
            self.press_key('2')
            self.assert_current_keychain('1', '2')
            self.assert_action(exp_action=exp_action, exp_count=exp_count, exp_widget=exp_widget)
            self.assert_active_keychains((('1', '2', 'A'), '12A in main'),
                                         (('1', '2', 'B'), '12B in main'))

        start_keychain(exp_action=None, exp_count=0, exp_widget=None)
        self.press_key('x')
        self.assert_action(exp_action=None, exp_count=0, exp_widget=None)
        self.assert_current_keychain()
        self.assert_active_keychains()


    def test_chain_with_builtin_key(self):
        self.km.bind('up down', 'jumping', context='item1')
        self.km.bind('up up', 'flying', context='item1')

        self.press_key('up')
        self.assert_current_keychain('up')
        self.assert_action(exp_action=None, exp_count=0, exp_widget=None)
        self.assert_active_keychains((('up', 'down'), 'jumping'),
                                     (('up', 'up'), 'flying'))
        self.press_key('down')
        self.assert_current_keychain()
        self.assert_action(exp_action='jumping', exp_count=1, exp_widget=self.listw1.focus)
        self.assert_active_keychains()

        self.press_key('up')
        self.assert_current_keychain('up')
        self.assert_action(exp_action='jumping', exp_count=1, exp_widget=self.listw1.focus)
        self.assert_active_keychains((('up', 'down'), 'jumping'),
                                     (('up', 'up'), 'flying'))
        self.press_key('up')
        self.assert_current_keychain()
        self.assert_action(exp_action='flying', exp_count=2, exp_widget=self.listw1.focus)
        self.assert_active_keychains()
