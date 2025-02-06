#!/usr/bin/python3
# filepath: monitor.py

import lcm
import time
import curses
import signal
from tabulate import tabulate
from procman3_messages import deputy_info_t, deputy_procs_t, proc_output_t

class ProcmanMonitor:
    def __init__(self):
        self.lc = lcm.LCM()
        self.deputies = {}  # deputy_name -> deputy_info
        self.processes = {} # proc_name -> proc_info
        self.outputs = {}   # proc_name -> stdout/stderr
        
        # Subscribe to status channels
        s1 = self.lc.subscribe("procman3/deputy_info", self.deputy_info_handler)
        s2 = self.lc.subscribe("procman3/deputy_procs", self.deputy_procs_handler)
        s3 = self.lc.subscribe("procman3/proc_outputs", self.proc_output_handler)
        
        s1.set_queue_capacity(1)
        s2.set_queue_capacity(1)
        s3.set_queue_capacity(3)

    def deputy_info_handler(self, channel, data):
        msg = deputy_info_t.decode(data)
        self.deputies[msg.deputy] = {
            'ip': msg.ip,
            'num_procs': msg.num_procs,
            'cpu': msg.cpu_usage,
            'mem': msg.mem_usage,
            'net_tx': msg.network_sent,
            'net_rx': msg.network_recv,
            'uptime': msg.uptime,
            'timestamp': msg.timestamp
        }

    def deputy_procs_handler(self, channel, data):
        msg = deputy_procs_t.decode(data)
        for proc in msg.procs:
            self.processes[proc.name] = {
                'group': proc.group,
                'deputy': msg.deputy,
                'status': proc.status,
                'cpu': proc.cpu,
                'mem': proc.mem,
                'pid': proc.pid,
                'errors': proc.errors,
                'timestamp': msg.timestamp
            }

    def proc_output_handler(self, channel, data):
        msg = proc_output_t.decode(data)
        if msg.stdout.strip():
            self.outputs[msg.name] = {
                'stdout': msg.stdout,
                'timestamp': msg.timestamp
            }

    def display_deputies(self):
        table = []
        headers = ['Deputy', 'IP', 'Procs', 'CPU%', 'Mem%', 'Net TX(KB)', 'Net RX(KB)', 'Uptime(s)']
        
        for name, info in self.deputies.items():
            table.append([
                name,
                info['ip'],
                info['num_procs'],
                f"{info['cpu']*100:.1f}",
                f"{info['mem']*100:.1f}",
                f"{info['net_tx']:.1f}",
                f"{info['net_rx']:.1f}",
                f"{info['uptime']}"
            ])
        
        return tabulate(table, headers=headers, tablefmt='grid')

    def display_processes(self):
        table = []
        headers = ['Name', 'Group', 'Deputy', 'Status', 'CPU%', 'Mem(KB)', 'PID', 'Errors']
        
        for name, info in self.processes.items():
            table.append([
                name,
                info['group'],
                info['deputy'],
                info['status'],
                f"{info['cpu']*100:.1f}",
                info['mem'],
                info['pid'],
                info['errors'][:30]  # Truncate long error messages
            ])
        
        return tabulate(table, headers=headers, tablefmt='grid')

    def display_outputs(self):
        output_text = "\nProcess Outputs:\n"
        for name, info in self.outputs.items():
            if info['stdout'].strip():
                output_text += f"\n=== {name} ===\n{info['stdout']}\n"
        return output_text
    
    def clear(self):
        self.processes.clear()
        self.deputies.clear()

    def run(self):
        try:
            while True:
                # Handle LCM messages
                self.lc.handle()

                # Clear screen
                print("\033[2J\033[H", end="")
                
                # Display tables
                print("\nDeputy Status:")
                print(self.display_deputies())
                print("\nProcess Status:")
                print(self.display_processes())
                print(self.display_outputs())

        except KeyboardInterrupt:
            print("\nExiting monitor...")

def main():
    monitor = ProcmanMonitor()
    monitor.run()

if __name__ == "__main__":
    main()