import lcm
import sys
import os
import time

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from procman3_messages import deputy_info_t, deputy_procs_t, proc_output_t, command_t
from PyQt5.QtCore import QThread, pyqtSignal


def seconds_to_hhmmss(seconds):
    return time.strftime('%H:%M:%S', time.gmtime(seconds))  

class LCMHandler(QThread):
    deputy_info_signal = pyqtSignal(dict)
    process_info_signal = pyqtSignal(dict)
    output_signal = pyqtSignal(dict)

    def __init__(self, udpm, hostname, deputy_info_channel, deputy_procs_channel, proc_output_channel):
        super().__init__()
        self.hostmname = hostname
        self.lc = lcm.LCM(udpm)
        self.deputies = {}
        self.processes = {}
        self.outputs = {}
        self.groups ={}

        self.deputy_info_channel = deputy_info_channel
        self.deputy_procs_channel = deputy_procs_channel
        self.proc_output_channel = proc_output_channel
        
        self.s1 = self.lc.subscribe(self.deputy_info_channel, self.deputy_info_handler)
        self.s2 = self.lc.subscribe(self.deputy_procs_channel, self.deputy_procs_handler)
        self.s3 = self.lc.subscribe(self.proc_output_channel, self.proc_output_handler)
        
    def change_udpm(self, udpm):
        self.lc = lcm.LCM(udpm)
        self.suscribre(self.deputy_info_channel, self.deputy_procs_channel, self.proc_output_channel)
        
    def change_channels(self, deputy_info_channel, deputy_procs_channel, proc_output_channel):
        self.unsubscribe(self.deputy_info_channel, self.deputy_procs_channel, self.proc_output_channel)
        self.suscribre(deputy_info_channel, deputy_procs_channel, proc_output_channel)
        self.deputy_info_channel = deputy_info_channel
        self.deputy_procs_channel = deputy_procs_channel
        self.proc_output_channel = proc_output_channel
        
    
    def unsubscribe(self, deputy_info_channel, deputy_procs_channel, proc_output_channel):
        # Unsubscribe from the current channels
        self.lc.unsubscribe(self.s1)
        self.lc.unsubscribe(self.s2)
        self.lc.unsubscribe(self.s3)
    
    def suscribre(self, deputy_info_channel, deputy_procs_channel, proc_output_channel):  
        #subscribe to the new channels
        self.s1 = self.lc.subscribe(deputy_info_channel, self.deputy_info_handler)
        self.s2 = self.lc.subscribe(deputy_procs_channel, self.deputy_procs_handler)
        self.s3 = self.lc.subscribe(proc_output_channel, self.proc_output_handler)
        
    def create_process(self, deputy, group, name, auto_restart, cmd, realtieme):
        msg = command_t()
        msg.name = name
        msg.group = group
        msg.deputy = deputy
        msg.command = "create_process"
        msg.proc_command = cmd
        msg.auto_restart = auto_restart
        msg.realtime = realtieme
        self.lc.publish("procman3/commands", msg.encode())
        
    def start_process(self, deputy, name):
        msg = command_t()
        msg.name = name
        msg.deputy = deputy
        msg.command = "start_process"
        self.lc.publish("procman3/commands", msg.encode())
        
    def stop_process(self, deputy, name):
        msg = command_t()
        msg.name = name
        msg.deputy = deputy
        msg.command = "stop_process"
        self.lc.publish("procman3/commands", msg.encode())
        
    def delete_process(self, deputy, name):
        msg = command_t()
        msg.name = name
        msg.deputy = deputy
        msg.command = "delete_process"
        self.lc.publish("procman3/commands", msg.encode())

    def deputy_info_handler(self, channel, data):
        msg = deputy_info_t.decode(data)
        now = time.time()
        
        self.deputies[msg.deputy] = {
            "ip": msg.ip,
            "num_procs": msg.num_procs,
            "cpu": msg.cpu_usage,
            "mem": msg.mem_usage,
            "net_tx": msg.network_sent,
            "net_rx": msg.network_recv,
            "uptime": msg.uptime,
            "timestamp": msg.timestamp,
            "last_update": now
        }
        self.deputy_info_signal.emit(self.deputies)

    def deputy_procs_handler(self, channel, data):
        msg = deputy_procs_t.decode(data)
        self.processes.clear()
        for proc in msg.procs:
            self.processes[proc.name] = {
                "group": proc.group,
                "deputy": msg.deputy,
                "status": proc.status,
                "cpu": proc.cpu,
                "mem": proc.mem,
                "pid": proc.pid,
                "errors": proc.errors,
                "timestamp": msg.timestamp,
                "exit_code": proc.exit_code,
                "priority": proc.priority,
                "runtime": proc.runtime,
                "cmd": proc.cmd,
                "auto_restart": proc.auto_restart,
                "realtime": proc.realtime
                
            }
            self.process_info_signal.emit(self.processes)

    def proc_output_handler(self, channel, data):
        msg = proc_output_t.decode(data)
        if msg.stdout.strip():
            self.outputs[msg.name] = {"stdout": msg.stdout, "timestamp": msg.timestamp}
        self.output_signal.emit(self.outputs)

    def run(self):
        while True:
            self.lc.handle_timeout(500)
