import subprocess
import unittest
from unittest.mock import patch,Mock
from logioptions import health


class HealthTests(unittest.TestCase):
    @patch('logioptions.health.subprocess.run')
    def test_service_reports_running_stopped_failed_missing_and_unavailable(self,run):
        for text,expected in [('LoadState=loaded\nActiveState=active\n','Running'),
                              ('LoadState=loaded\nActiveState=inactive\n','Stopped'),
                              ('LoadState=loaded\nActiveState=failed\nResult=exit-code\n','Failed'),
                              ('LoadState=not-found\nActiveState=inactive\n','Not installed')]:
            run.return_value=Mock(returncode=0,stdout=text)
            self.assertEqual(health.service_status('test.service')['status'],expected)
        run.side_effect=subprocess.TimeoutExpired('systemctl',5)
        self.assertEqual(health.service_status('test.service')['status'],'Unavailable')

    @patch('logioptions.ring.shell_call')
    def test_ready_and_outdated_extension_are_distinguished(self,call):
        call.side_effect=[Mock(unpack=lambda:('ready',)),Mock(unpack=lambda:(1,))]
        self.assertEqual(health.extension_status()['status'],'Ready')
        call.side_effect=[Mock(unpack=lambda:('ready',)),RuntimeError('Unknown method')]
        result=health.extension_status()
        self.assertEqual(result['status'],'Update needs a new login')
        self.assertIn('Actions Ring is available',result['detail'])

    @patch('logioptions.health.extension_info')
    @patch('logioptions.ring.shell_call',side_effect=RuntimeError('endpoint absent'))
    def test_disabled_missing_and_broken_extension_guidance(self,call,info):
        for data,expected in [({},'Not installed'),({'state':2,'enabled':False},'Disabled'),
                              ({'state':3,'enabled':True},'Failed to load'),
                              ({'state':4,'enabled':True},'Incompatible')]:
            info.return_value=data
            self.assertEqual(health.extension_status()['status'],expected)
        info.side_effect=RuntimeError('No GNOME bus')
        self.assertEqual(health.extension_status()['status'],'Unavailable')

    @patch('logioptions.health.subprocess.run')
    def test_restart_only_restarts_listener_and_propagates_failure(self,run):
        health.restart_background()
        self.assertEqual(run.call_args.args[0],['systemctl','--user','restart','logioptions-ring.service'])
        self.assertTrue(run.call_args.kwargs['check'])
        run.side_effect=subprocess.CalledProcessError(1,'systemctl',stderr='Restart denied')
        with self.assertRaises(subprocess.CalledProcessError):health.restart_background()

    @patch('logioptions.health.read_rows')
    def test_device_diagnostic_does_not_claim_stale_readings_are_live(self,read):
        read.return_value=[]
        self.assertEqual(health.device_status()['status'],'Waiting for devices')
        read.return_value=[dict(name='Mouse',percentage=70,updated=1)]
        self.assertEqual(health.device_status()['status'],'No recent device replies')
