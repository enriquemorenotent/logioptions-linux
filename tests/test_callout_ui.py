import os
import time
import unittest
from unittest.mock import patch
try:
    from logioptions.gui import OptionsApp,OptionsWindow,Gtk,GLib
except ImportError:
    Gtk=None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST')=='1'
                    and os.environ.get('GDK_BACKEND')=='x11','Requires isolated GTK display')
class CalloutUITests(unittest.TestCase):
    def test_lines_match_dots_and_boxes_fit_with_panel_open(self):
        app=OptionsApp();app.set_application_id('local.logioptions.CalloutUITest');app.register(None)
        def frames():
            until=time.monotonic()+.12
            while time.monotonic()<until:
                while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
                time.sleep(.002)
        with patch.object(OptionsWindow,'refresh'),patch('logioptions.button_actions.for_device',return_value={'82':{'type':'shortcut','keys':['Control_L','Shift_L','Alt_L','Super_L','F12']}}):
            window=OptionsWindow(app)
            window.devices=[dict(key='test',name='MX Master 4',kind_code=3,controls=[
                dict(index=i,control_id=cid,flags=0x30,group=1,group_mask=1,reporting={'remapped_to':cid})
                for i,cid in enumerate((82,195,196,86,416,83))])]
            try:
                window.render_device();window.present();frames()
                image=window.device_picture
                for panel in (False,True):
                    if panel:window.show_panel('Button actions');window.set_default_size(1000,760)
                    frames()
                    self.assertEqual(len(window.connector_records),7)
                    boxes=[]
                    for record in window.connector_records:
                        ok,dot=record['dot'].compute_bounds(window.canvas)
                        self.assertTrue(ok)
                        x,y=record['points'][0]
                        self.assertAlmostEqual(x,dot.get_x()+dot.get_width()/2,delta=1)
                        self.assertAlmostEqual(y,dot.get_y()+dot.get_height()/2,delta=1)
                        ok,rect=record['button'].compute_bounds(window.canvas)
                        self.assertTrue(ok)
                        boxes.append(rect)
                        self.assertGreaterEqual(rect.get_x(),0)
                        self.assertGreaterEqual(rect.get_y(),0)
                        self.assertLessEqual(rect.get_x()+rect.get_width(),window.canvas.get_width()+1)
                        self.assertLessEqual(rect.get_y()+rect.get_height(),window.canvas.get_height()+1)
                    for i,a in enumerate(boxes):
                        for b in boxes[i+1:]:
                            self.assertTrue(a.get_x()+a.get_width()<=b.get_x()+1 or b.get_x()+b.get_width()<=a.get_x()+1 or
                                            a.get_y()+a.get_height()<=b.get_y()+1 or b.get_y()+b.get_height()<=a.get_y()+1,
                                f'panel={panel}, canvas={window.canvas.get_width()}x{window.canvas.get_height()}, a={(a.get_x(),a.get_y(),a.get_width(),a.get_height())}, b={(b.get_x(),b.get_y(),b.get_width(),b.get_height())}, planned={window.callout_positions}')
                    for rect in boxes:
                        for record in window.connector_records:
                            x,y=record['points'][0]
                            self.assertFalse(rect.get_x()<=x<=rect.get_x()+rect.get_width() and
                                             rect.get_y()<=y<=rect.get_y()+rect.get_height())
                    self.assertIs(window.device_picture,image)
                    self.assertTrue(image.get_mapped())
                record=window.connector_records[1]
                record['button'].add_css_class('selected')
                self.assertTrue(record['active'])
                self.assertTrue(record['dot'].has_css_class('active'))
            finally:
                window.on_close();window.destroy()
