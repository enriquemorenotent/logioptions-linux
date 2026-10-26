"""Exercise live assignment changes and reconnection with one real reader thread."""
import queue
import threading
import unittest
from logioptions.ring import RingListener


class ButtonListenerTests(unittest.TestCase):
    def start_listener(self, configured, *, identity=None, api=True):
        reports = queue.Queue()
        ready = threading.Event()
        states = {83:{'flags':0,'remapped_to':86},416:{'flags':0,'remapped_to':416}}
        writes, executed, calls, errors = [], [], [], []
        current_identity = [identity]
        class Transport:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read_notification(self, timeout):
                ready.set()
                try: report = reports.get(timeout=.01)
                except queue.Empty: return None
                if isinstance(report, threading.Event):
                    report.set()
                    return None
                return report
        class Device:
            def __init__(self, transport, index): self.device_index=index
            def feature(self, _): return {'index':13}
            def identity(self, timeout): return current_identity[0]
            def control_reporting(self, cid): return dict(states[cid])
            def set_control_reporting_bytes(self, cid, flags, target):
                writes.append((cid,flags,target,current_identity[0]))
                states[cid]={'flags':flags & 1,'remapped_to':target}
        descriptor={'path':'fake','device_index':2,'controls':[{'control_id':c,'flags':0x30} for c in states]}
        if identity: descriptor['identity']=identity
        listener=RingListener(descriptor,errors.append,transport_factory=Transport,device_factory=Device,
            call=calls.append,bindings=lambda:configured.copy(),button_api=lambda:api,
            execute=executed.append,health_interval=.005)
        self.addCleanup(listener.stop)
        self.assertTrue(ready.wait(2))
        def feed(*held):
            report=bytes([0x11,2,13,0])+b''.join(cid.to_bytes(2,'big') for cid in held)
            reports.put(report.ljust(20,b'\0'))
            barrier=threading.Event();reports.put(barrier)
            self.assertTrue(barrier.wait(2))
        def maintenance():
            # Each empty read allows the real maintenance clock to advance.
            done=threading.Event()
            timer=threading.Timer(.03,done.set);timer.start()
            self.assertTrue(done.wait(1))
        return listener,states,writes,executed,calls,errors,current_identity,feed,maintenance

    def test_changing_action_while_held_waits_for_a_new_press(self):
        copy={'type':'shortcut','keys':['Control_L','c']}
        paste={'type':'shortcut','keys':['Control_L','v']}
        configured={'83':copy}
        listener,states,writes,executed,calls,errors,identity,feed,maintenance=self.start_listener(configured)
        feed(83)
        self.assertEqual(executed,[copy])
        configured['83']=paste
        maintenance()
        feed(83)
        self.assertEqual(executed,[copy])
        feed();feed(83)
        self.assertEqual(executed,[copy,paste])
        listener.stop()
        self.assertEqual(states[83],{'flags':0,'remapped_to':86})

    def test_removing_action_restores_button_without_stopping_ring(self):
        configured={'83':{'type':'shortcut','keys':['Control_L','c']}}
        listener,states,writes,executed,calls,errors,identity,feed,maintenance=self.start_listener(configured)
        configured.clear()
        maintenance()
        self.assertEqual(states[83],{'flags':0,'remapped_to':86})
        self.assertEqual(states[416]['flags'],1)
        feed(416);feed()
        self.assertIn('Show',calls)
        self.assertIn('Release',calls)
        self.assertTrue(listener.thread.is_alive())

    def test_receiver_slot_reuse_never_writes_previous_settings_to_new_device(self):
        configured={'83':{'type':'shortcut','keys':['Control_L','c']}}
        listener,states,writes,executed,calls,errors,identity,feed,maintenance=self.start_listener(configured,identity='mouse-a')
        identity[0]='mouse-b'
        listener.thread.join(2)
        self.assertFalse(listener.thread.is_alive())
        self.assertTrue(any('Mouse changed receiver slots' in message for message in errors))
        self.assertTrue(writes)
        self.assertTrue(all(write[3]=='mouse-a' for write in writes))

    def test_old_extension_leaves_custom_buttons_undiverted(self):
        configured={'83':{'type':'shortcut','keys':['Control_L','c']}}
        listener,states,writes,executed,calls,errors,identity,feed,maintenance=self.start_listener(configured,api=False)
        self.assertEqual(states[83]['flags'],0)
        self.assertEqual(states[416]['flags'],1)
        feed(83)
        self.assertEqual(executed,[])
        self.assertTrue(any('updated GNOME extension' in message for message in errors))

    def test_reconnect_rearms_saved_shortcut_after_device_resets_reporting(self):
        action={'type':'shortcut','keys':['Control_L','c']}
        listener,states,writes,executed,calls,errors,identity,feed,maintenance=self.start_listener({'83':action})
        states[83]['flags']=0
        maintenance()
        self.assertEqual(states[83]['flags'],1)
        feed(83)
        self.assertEqual(executed,[action])
        self.assertTrue(any('recovered' in message for message in errors))

    def test_replacing_held_ring_assignment_closes_the_open_ring(self):
        action={'type':'shortcut','keys':['Control_L','c']}
        configured={'83':{'type':'ring'}}
        listener,states,writes,executed,calls,errors,identity,feed,maintenance=self.start_listener(configured)
        feed(83)
        self.assertEqual(calls,['Show'])
        configured['83']=action
        maintenance()
        self.assertEqual(calls,['Show','Hide'])
        feed(83);feed()
        self.assertEqual(executed,[])
        self.assertNotIn('Release',calls)
        feed(83)
        self.assertEqual(executed,[action])
