import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from logioptions import button_actions as actions
from logioptions.ring import RingListener


class ButtonActionsTests(unittest.TestCase):
    def test_persistence_validation_and_device_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_CONFIG_HOME=directory):
            action = {'type':'shortcut', 'keys':['Control_L','c']}
            actions.save('mouse-a', 83, action)
            self.assertEqual(actions.for_device('mouse-a'), {'83':action})
            self.assertEqual(actions.for_device('mouse-b'), {})
            self.assertEqual(actions.path().stat().st_mode & 0o777, 0o600)
            before = actions.path().read_bytes()
            for value in ({'type':'shell','command':'something'}, {'type':'shortcut','keys':['Control_L']},
                          {'type':'desktop','action':'unknown'}, {'type':'shortcut','keys':['c','v']}):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    actions.save('mouse-a', 83, value)
                self.assertEqual(actions.path().read_bytes(), before)
            for cid in (80,81):
                with self.assertRaises(ValueError): actions.save('mouse-a',cid,action)
            actions.save('mouse-a',83,None)
            self.assertEqual(actions.for_device('mouse-a'), {})

    def test_listener_dispatches_once_and_restores_all_controls(self):
        fired = threading.Event()
        instances, events = [], []
        class Transport:
            def __init__(self, path):
                # Same held report repeated; only a transition may execute.
                press = bytes.fromhex('11020d00005301a0000000000000000000000000')
                self.reports = [press, press, bytes.fromhex('11020d0000000000000000000000000000000000')]
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read_notification(self, timeout):
                if self.reports: return self.reports.pop(0)
                threading.Event().wait(.005)
        class Device:
            def __init__(self, transport, index):
                self.device_index = index
                self.states = {83:{'flags':0,'remapped_to':86},416:{'flags':0,'remapped_to':416}}
                instances.append(self)
            def feature(self, _): return {'index':13}
            def control_reporting(self, cid): return dict(self.states[cid])
            def set_control_reporting_bytes(self, cid, flags, target):
                self.states[cid] = {'flags':flags & 1, 'remapped_to':target}
        action = {'type':'shortcut','keys':['Control_L','c']}
        executed = []
        def call(method):
            events.append(method)
            if method == 'Release': fired.set()
        listener = RingListener({'path':'fake','device_index':2,'controls':[{'control_id':c,'flags':0x20} for c in (83,416)]},
            transport_factory=Transport, device_factory=Device, call=call,
            bindings=lambda:{'83':action}, button_api=lambda:True, execute=executed.append)
        try:
            self.assertTrue(fired.wait(2))
            self.assertEqual(executed,[action])
        finally: listener.stop()
        self.assertEqual(instances[0].states, {83:{'flags':0,'remapped_to':86},416:{'flags':0,'remapped_to':416}})
        self.assertEqual(events,['Show','Release','Hide'])

    def test_failed_diversion_setup_restores_previously_changed_buttons(self):
        errors, instances = [], []
        class Transport:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Device:
            def __init__(self, transport, index):
                self.device_index = index
                self.states = {83:{'flags':0,'remapped_to':83},86:{'flags':0,'remapped_to':86}}
                instances.append(self)
            def feature(self, _): return {'index':13}
            def control_reporting(self, cid): return dict(self.states[cid])
            def set_control_reporting_bytes(self, cid, flags, target):
                if cid == 86 and flags == 3: raise RuntimeError('Second control rejected diversion')
                self.states[cid] = {'flags':flags & 1,'remapped_to':target}
        action = {'type':'shortcut','keys':['Control_L','c']}
        listener = RingListener({'path':'fake','device_index':2,'controls':[{'control_id':c,'flags':0x20} for c in (83,86)]},
            errors.append, transport_factory=Transport, device_factory=Device, call=lambda _:None,
            bindings=lambda:{'83':action,'86':action}, button_api=lambda:True)
        listener.thread.join(2)
        self.assertFalse(listener.thread.is_alive())
        self.assertTrue(any('rejected diversion' in error for error in errors))
        self.assertEqual(instances[0].states,{83:{'flags':0,'remapped_to':83},86:{'flags':0,'remapped_to':86}})

    def test_extension_validation_and_execution(self):
        root = Path(__file__).resolve().parents[1]
        extension = root/'extensions/logioptions-ring@local'
        script = r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {validateButtonAction} from BUTTONS;
assert.deepEqual(validateButtonAction({type:'shortcut',keys:['Control_L','c']}),{type:'shortcut',keys:['Control_L','c']});
for (const value of [{type:'shell',command:'anything'}, {type:'shortcut',keys:['Super_L']}, {type:'shortcut',keys:['c','v']}])
 assert.throws(()=>validateButtonAction(value));
const source = fs.readFileSync(EXTENSION,'utf8').replace(/^import .*;$/gm,'').replace('export default class ActionsRing','class ActionsRing')+'\nActionsRing';
const events=[];
const Main={sessionMode:{isLocked:false,isGreeter:false},overview:{toggle:()=>events.push('overview')}};
const klass=vm.runInNewContext(source,{Extension:class{},validateButtonAction,Main,global:{display:{focus_window:{}},workspace_manager:{get_active_workspace:()=>({})}},
 Clutter:{KEY_Control_L:65507,KEY_c:99,KeyState:{PRESSED:1,RELEASED:0}},GLib:{get_monotonic_time:()=>1}});
const instance=new klass();
instance._keyboard={notify_keyval:(now,value,state)=>events.push([value,state])};
instance.ExecuteButton(JSON.stringify({type:'shortcut',keys:['Control_L','c']}));
assert.deepEqual(events,[[65507,1],[99,1],[99,0],[65507,0]]);
events.length=0;
Main.sessionMode.isLocked=true;
instance.ExecuteButton(JSON.stringify({type:'shortcut',keys:['Control_L','c']}));
assert.deepEqual(events,[]);
Main.sessionMode.isLocked=false;
assert.throws(()=>instance.ExecuteButton(JSON.stringify({type:'shortcut',keys:['UnknownKey']})));
assert.deepEqual(events,[]);
instance.ExecuteButton(JSON.stringify({type:'desktop',action:'overview'}));
assert.deepEqual(events,['overview']);
events.length=0;
instance._keyboard={notify_keyval:(now,value,state)=>{events.push([value,state]); if (value===99 && state===1) throw new Error('injection failed');}};
assert.throws(()=>instance.ExecuteButton(JSON.stringify({type:'shortcut',keys:['Control_L','c']})));
assert.deepEqual(events,[[65507,1],[99,1],[99,0],[65507,0]]);
'''.replace('BUTTONS',json.dumps((extension/'buttons.js').as_uri())).replace('EXTENSION',json.dumps(str(extension/'extension.js')))
        subprocess.run(['node','--input-type=module','-e',script],check=True,capture_output=True)
