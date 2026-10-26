import unittest
from logioptions.button_labels import assignment_label,action_label,shortcut_label


class ButtonLabelTests(unittest.TestCase):
    def test_common_custom_desktop_and_ring_labels(self):
        self.assertEqual(action_label({'type':'shortcut','keys':['Control_L','c']}),'Copy · Ctrl+C')
        self.assertEqual(action_label({'type':'shortcut','keys':['Control_L','Shift_L','F12']}),'Ctrl+Shift+F12')
        self.assertEqual(action_label({'type':'desktop','action':'overview'}),'Show overview')
        self.assertEqual(action_label({'type':'ring'}),'Actions Ring')
        self.assertEqual(shortcut_label(['Super_L','Page_Up']),'Super+Page Up')

    def test_saved_host_action_wins_over_hardware_mapping(self):
        descriptor={'controls':[{'control_id':83,'flags':0x30,'reporting':{'remapped_to':86}}]}
        self.assertEqual(assignment_label(descriptor,83,{}),'Forward')
        self.assertEqual(assignment_label(descriptor,83,{'83':{'type':'shortcut','keys':['Control_L','c']}}),'Copy · Ctrl+C')
        self.assertEqual(assignment_label(descriptor,82,{}),'Action unavailable')

    def test_thumb_pad_default_and_override(self):
        descriptor={'controls':[{'control_id':416,'flags':0x20}]}
        self.assertEqual(assignment_label(descriptor,416,{}),'Actions Ring')
        self.assertEqual(assignment_label(descriptor,416,{'416':{'type':'desktop','action':'show_desktop'}}),'Show desktop')
