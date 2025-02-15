import lcm
import sys
import os
import time

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from procman3_messages import host_info_t, host_procs_t, proc_info_t, proc_output_t, command_t
from PyQt5.QtCore import QThread, pyqtSignal


def seconds_to_hhmmss(seconds):
    return time.strftime('%H:%M:%S', time.gmtime(seconds))  

class LCMHandler(QThread):
    host_info_signal = pyqtSignal(dict)
    process_info_signal = pyqtSignal(dict)
    output_signal = pyqtSignal(dict)

    def __init__(self, udpm, hostname, host_info_channel, host_procs_channel, proc_output_channel):
        super().__init__()
        self.hostmname = hostname
        self.lc = lcm.LCM(udpm)
        self.hosts = {}
        self.processes = {}
        self.outputs = {}
        self.groups ={}

        self.host_info_channel = host_info_channel
        self.host_procs_channel = host_procs_channel
        self.proc_output_channel = proc_output_channel
        
        self.s1 = self.lc.subscribe(self.host_info_channel, self.host_info_handler)
        self.s2 = self.lc.subscribe(self.host_procs_channel, self.host_procs_handler)
        self.s3 = self.lc.subscribe(self.proc_output_channel, self.proc_output_handler)
        
    def change_udpm(self, udpm):
        self.lc = lcm.LCM(udpm)
        self.suscribe(self.host_info_channel, self.host_procs_channel, self.proc_output_channel)
        
    def change_channels(self, host_info_channel, host_procs_channel, proc_output_channel):
        self.unsubscribe()
        self.suscribe(host_info_channel, host_procs_channel, proc_output_channel)
        self.host_info_channel = host_info_channel
        self.host_procs_channel = host_procs_channel
        self.proc_output_channel = proc_output_channel
        
    
    def unsubscribe(self):
        # Unsubscribe from the current channels
        self.lc.unsubscribe(self.s1)
        self.lc.unsubscribe(self.s2)
        self.lc.unsubscribe(self.s3)
    
    def suscribe(self, host_info_channel, host_procs_channel, proc_output_channel):  
        #subscribe to the new channels
        self.s1 = self.lc.subscribe(host_info_channel, self.host_info_handler)
        self.s2 = self.lc.subscribe(host_procs_channel, self.host_procs_handler)
        self.s3 = self.lc.subscribe(proc_output_channel, self.proc_output_handler)
        
    def create_process(self, hostname, group, name, auto_restart, cmd, realtieme):
        msg = command_t()
        msg.name = name
        msg.group = group
        msg.hostname = hostname
        msg.command = "create_process"
        msg.proc_command = cmd
        msg.auto_restart = auto_restart
        msg.realtime = realtieme
        self.lc.publish("procman3/commands", msg.encode())
        
    def start_process(self, hostname, name):
        msg = command_t()
        msg.name = name
        msg.hostname = hostname
        msg.command = "start_process"
        self.lc.publish("procman3/commands", msg.encode())
        
    def stop_process(self, hostname, name):
        msg = command_t()
        msg.name = name
        msg.hostname = hostname
        msg.command = "stop_process"
        self.lc.publish("procman3/commands", msg.encode())
        
    def delete_process(self, hostname, name):
        msg = command_t()
        msg.name = name
        msg.hostname = hostname
        msg.command = "delete_process"
        self.lc.publish("procman3/commands", msg.encode())

    def host_info_handler(self, channel, data):
        msg = host_info_t.decode(data)
        now = time.time()
        
        self.hosts[msg.hostname] = {
            "ip": msg.ip,
            "cpus": msg.cpus,
            "cpu_usage": msg.cpu_usage,
            "mem_total": msg.mem_total,
            "mem_free": msg.mem_free,
            "mem_used": msg.mem_usage,
            "mem_usage": msg.mem_usage,
            "net_tx": msg.network_sent,
            "net_rx": msg.network_recv,
            "uptime": msg.uptime,
            "timestamp": msg.timestamp,
            "last_update": now
        }
        self.host_info_signal.emit(self.hosts)

    def host_procs_handler(self, channel, data):
        msg = host_procs_t.decode(data)
        self.processes.clear()
        for proc in msg.procs:
            self.processes[proc.name] = {
                "group": proc.group,
                "hostname": msg.hostname,
                "state": proc.state,
                "status": proc.status,
                "errors": proc.errors,
                "cmd": proc.cmd,
                "cpu": proc.cpu,
                "mem_rss": proc.mem_rss,
                "mem_vms": proc.mem_vms,
                "priority": proc.priority,
                "pid": proc.pid,
                "ppid": proc.ppid,
                "auto_restart": proc.auto_restart,
                "realtime": proc.realtime,
                "exit_code": proc.exit_code,
                "runtime": proc.runtime
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
