#!/usr/bin/python3
# filepath: monitor.py

import lcm
import time
from tabulate import tabulate
import curses
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from procman3_messages import host_info_t, host_procs_t, proc_output_t

class ProcmanMonitor:
    def __init__(self):
        self.lc = lcm.LCM()
        self.hosts = {}  
        self.processes = {} 
        self.outputs = {}   
        
        # Subscribe to status channels
        s1 = self.lc.subscribe("procman3/host_info", self.host_info_handler)
        s2 = self.lc.subscribe("procman3/host_procs", self.host_procs_handler)
        s3 = self.lc.subscribe("procman3/proc_outputs", self.proc_output_handler)
        
        s1.set_queue_capacity(1)
        s2.set_queue_capacity(1)
        s3.set_queue_capacity(3)

    def host_info_handler(self, channel, data):
        msg = host_info_t.decode(data)
        self.hosts[msg.hostname] = {
            'timestamp': msg.timestamp,
            'ip': msg.ip,
            'cpus': msg.cpus,
            'mem_total': msg.mem_total,
            'mem_free': msg.mem_free,
            'mem_usage': msg.mem_usage,
            'cpu_usage': msg.cpu_usage,
            'net_tx': msg.network_sent,
            'net_rx': msg.network_recv,
            'uptime': msg.uptime
        }

    def host_procs_handler(self, channel, data):
        msg = host_procs_t.decode(data)
        self.processes.clear()
        for proc in msg.procs:
            self.processes[proc.name] = {
                'group': proc.group,
                'hostname': msg.hostname,
                'status': proc.status,
                'state': proc.state,
                'errors': proc.errors,
                'cmd': proc.cmd,
                'cpu': proc.cpu,
                'mem_rss': proc.mem_rss,
                'mem_vms': proc.mem_vms,
                'priority': proc.priority,
                'pid': proc.pid,
                'ppid': proc.ppid,
                'auto_restart': proc.auto_restart,
                'realtime': proc.realtime,
            }

    def proc_output_handler(self, channel, data):
        msg = proc_output_t.decode(data)
        if msg.stdout.strip():
            self.outputs[msg.name] = {
                'stdout': msg.stdout,
                'stderr': msg.stderr,
                'timestamp': msg.timestamp
            }

    def display_hosts(self):
        table = []
        headers = ['Deputy', 'IP', 'CPU%', 'Mem%', 'Net TX(kB/s)', 'Net RX(kB/s)', 'Uptime(s)']
        
        for name, info in self.hosts.items():
            table.append([
                name,
                info['ip'],
                f"{info['cpu_usage']*100:.1f}",
                f"{info['mem_usage']*100:.1f}",
                f"{info['net_tx']:.1f}",
                f"{info['net_rx']:.1f}",
                f"{info['uptime']}"
            ])
        
        #return tabulate(table, headers=headers, tablefmt='github')
        return tabulate(table, headers=headers)
    
    def display_processes(self):
        grouped_processes = {}
        for name, info in self.processes.items():
            group = info['group']
            if group not in grouped_processes:
                grouped_processes[group] = []
            grouped_processes[group].append((name, info))
    
        output = ""
        headers = ['Group', 'Name', 'Host', 'Status', 'CPU%', 'Mem(KB)', 'PID', 'Priority', 'Errors']
        colalign = ['left', 'left', 'left'  , 'center', 'right', 'right', 'right', 'right'  , 'left']
        table = []
    
        for group, processes in grouped_processes.items():
            # Calculate totals for group
            total_cpu = sum(info['cpu'] for _, info in processes)
            total_mem = sum(info['mem_rss'] for _, info in processes)
            statuses = [info['state'] for _, info in processes]
            
            if all(status == 'R' for status in statuses):
                group_status = 'Running'
            elif all(status == 'T' for status in statuses):
                group_status = 'Stopped'
            else:
                group_status = 'Mixed'
            
            table.append([group, '', '', group_status, f"{total_cpu*100:.1f}", total_mem, '', '', ''])  # Add group row with totals and status
            
            
            for name, info in processes:
                table.append([
                    '',  # Empty cell for group
                    f"  {name}",  # Indent process name
                    info['hostname'],
                    info['state'],
                    f"{info['cpu']*100:.1f}",
                    info['mem_rss']*1,
                    info['pid']*1,
                    info['priority'],
                    info['errors'][:30]
                ])

        #table = tabulate(table, headers=headers, tablefmt='github', numalign="right" )
        table = tabulate(table, headers=headers) 
        output += table
        return output

    def display_outputs(self, num_lines=7):
        output_text = "\nProcess Outputs:\n"
        for name, info in self.outputs.items():
            if info['stdout'].strip():
                truncated_output = '\n'.join(info['stdout'].splitlines()[:num_lines])  # Get the first num_lines of the output
                output_text += f"\n=== {name} ===\n{truncated_output}\n"
        return output_text
    
    def clear(self):
        self.processes.clear()
        self.deputies.clear()

    def run(self):
        try:
            while True:
                # Handle LCM messages
                self.lc.handle_timeout(50)

                # Clear screen
                print("\033[2J\033[H", end="")
                
                # Display tables
                print("\nDeputy Status:")
                print(self.display_hosts())
                print("\nProcess Status:")
                print(self.display_processes())
                #print("\nProcess Outputs:")
                #print(self.display_outputs())

        except KeyboardInterrupt:
            print("\nExiting monitor...")

def main():
    monitor = ProcmanMonitor()
    monitor.run()

if __name__ == "__main__":
    main()