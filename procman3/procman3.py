#!/usr/bin/env python3
import os
import time
import lcm
import psutil
from subprocess import PIPE
import logging
import socket
import yaml
import fcntl
import sys

# Import LCM message types from ../procman3_messages
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from procman3_messages import command_t, host_info_t, host_procs_t, proc_info_t, proc_output_t

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class Timer:
    def __init__(self, timeout):
        now = time.time()
        self.t0 = now
        self.period = timeout
        self.next = now + timeout

    def timeout(self):
        now = time.time()
        if now > self.next:
            self.next +=self.period
            return True
        else:
            return False

def set_nonblocking(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)


def is_running(proc):
    if proc is None:    
        return False
    if proc.poll() is not None:
        return False
    else:
        return True
    
   
class Procman3:
    def __init__(self, config_file="procman3.yaml"):
        # Load configuration from YAML file
        #get the directory of the current file
        current_dir = os.path.dirname(os.path.realpath(__file__))
        config_file = os.path.join(current_dir, config_file)
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        
        self.processes = {}
        
        self.lc = lcm.LCM()
        
        self.command_channel = config['command_channel']
        self.deputy_info_channel = config['deputy_info_channel']
        self.proc_outputs_channel = config['proc_outputs_channel']
        self.deputy_procs_channel = config['deputy_procs_channel']
        self.stop_timeout = config['stop_timeout']
        
        self.last_publish_time = 0
        self.last_net_tx = 0
        self.last_net_rx = 0
        
        self.monitor_timer = Timer(config['monitor_interval'])
        self.output_timer = Timer(config['output_interval'])
        self.host_status_timer = Timer(config['deputy_status_interval'])
        self.procs_status_timer = Timer(config['procs_status_interval'])
        
        self.hostname = socket.gethostname() 
        self.subscription = self.lc.subscribe(self.command_channel, self.command_handler)
        
        # Configure logging
        #get the directory of the current file
        current_dir = os.path.dirname(os.path.realpath(__file__))
        log_dir = os.path.join(current_dir, './log/')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, "procman3.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logging.info(f"Deputy initialized with channels: "
                     f"command_channel={self.command_channel}, "
                     f"deputy_info_channel={self.deputy_info_channel}, "
                     f"proc_outputs_channel={self.proc_outputs_channel}, "
                     f"deputy_procs_channel={self.deputy_procs_channel}")


    def command_handler(self, channel, data):
        msg = command_t.decode(data)
        if msg.hostname != self.hostname:
            logging.info(f"Command handler: Ignored command for deputy {msg.deputy}")
            return

        logging.info(f"Command handler: Received command: {msg.command} for process: {msg.proc_command}")
        group = msg.group
        
        
        if msg.command == "create_process":
            self.create_process(msg.name, msg.proc_command, msg.auto_restart, msg.realtime, group)
        
        elif msg.command == "start_process":
            self.start_process(msg.name)
            
        elif msg.command == "stop_process":
            self.stop_process(msg.name)
                
        elif msg.command == "delete_process":
            self.delete_process(msg.name)
            
        else:
            logging.warning(f"Command handler: Unknown command: {msg.command} for process: {msg.proc_command}")

    def create_process(self, process_name, proc_command, restart_on_failure, realtime, group):
        
        # if proc exist first we stop it, then we modify the process
        if process_name in self.processes:
            proc_info = self.processes[process_name]
            proc = proc_info['proc']
            if is_running(proc):
                self.stop_process(process_name)
                
        self.processes[process_name] = {'proc': None, 'cmd': proc_command,'restart': restart_on_failure, 'realtime': realtime,
                                        'exit_code': -1, 'group': group, 'errors': '', 'state': 'T', 'status': 'S', 'runtime': 0,
                                        'stdout': '', 'stderr': ''} 
        
        logging.info(f"Create Process: Created process: {process_name} with command: {proc_command} auto_restart: {restart_on_failure} and realtime: {realtime}")
            
            
    def start_process(self, process_name):
        
        if process_name not in self.processes:
            logging.warning(f"Start Process: Process {process_name} not found in the process table. Ignoring command.")
            return
       
        # here the process exists in the process table, check if it is running
        proc_info = self.processes[process_name]
        proc = proc_info['proc']
        proc_command = proc_info['cmd']
        realtime = proc_info['realtime']
        
        if is_running(proc):    
            logging.info(f"Start Process: Process {process_name} is already running with PID {proc.pid}. Skipping start.")
        
        else:
            #start the process
            logging.info(f"Start Process: Starting process: {process_name} with command: {proc_command}")      
            try:
                proc = psutil.Popen([proc_command], stdout=PIPE, stderr=PIPE)
                set_nonblocking(proc.stdout) # Set non-blocking mode for stdout
                set_nonblocking(proc.stderr) # Set non-blocking mode for stderr
                
                # update the process table with the new process
                self.processes[process_name]['proc'] = proc
                self.processes[process_name]['state'] = 'R'                
                logging.info(f"Start Process: Started process: {process_name} with PID {proc.pid}")

                if realtime:
                    try:
                        os.sched_setscheduler(proc.pid, os.SCHED_FIFO, os.sched_param(40))
                        logging.info(f"Start Process: Set real-time priority and FIFO scheduler for process: {process_name} with PID {proc.pid}")
                    except PermissionError:
                        logging.error(f"Start Process: Failed to set real-time priority for process {process_name}: Permission denied.")
                        self.processes[process_name]['errors'] = f"Failed to set real-time priority for process {process_name}: Permission denied."
                    except Exception as e:
                        logging.error(f"Start Process: Failed to set real-time priority for process {process_name}: {e}")
                        self.processes[process_name]['errors'] = str(e)

            except Exception as e:
                logging.error(f"Start Process: Failed to start process {process_name}: {e}")
                self.processes[process_name]['state'] = 'F'
                self.processes[process_name]['proc'] = None
                self.processes[process_name]['errors'] = str(e)
        
    
    def stop_process(self, process_name):
        if process_name in self.processes:
            proc_info = self.processes[process_name]
            proc = proc_info['proc']
            
            if(proc and proc_info['state'] == 'T'):
                logging.info(f"Stop Process: Process {process_name} is already stopped.")
                return
            
            if proc is None:
                logging.info(f"Stop Process: Process {process_name} not running, ignoring command.")
                return
            try:
                proc.terminate()
                proc.wait(timeout=self.stop_timeout)  # Use the stop timeout variable
                logging.info(f"Stop Process: Gracefully stopped process: {process_name} with PID {proc.pid}")
                self.processes[process_name]['exit_code'] = proc.returncode
                self.processes[process_name]['state'] = 'T'
                
            except psutil.TimeoutExpired:
                proc.kill()  # Force kill
                logging.warning(f"Stop Process: Forcefully killed process: {process_name} with PID {proc.pid}")
                self.processes[process_name]['exit_code'] = proc.returncode
                self.processes[process_name]['state'] = 'K'
            
        else:
            logging.warning(f"Stop Process: Process {process_name} not found, ignoring command.")

    def delete_process(self, process_name):
        if process_name in self.processes:
            if self.processes[process_name]['proc'] is not None:
                self.stop_process(process_name)
                
            del self.processes[process_name]
            logging.info(f"Delete Process: Deleted process: {process_name}")
        else:
            logging.warning(f"Delete Process: Process {process_name} not found, ignoring command.")
        
    
    def monitor_process(self, process_name):
        
        #check if process_name is in the process table
        if process_name not in self.processes:
            logging.warning(f"Monitor Process: Process {process_name} not found in process table.")
            return
        
        procces = self.processes[process_name]
        proc = procces['proc']
               
        # check if the process is stoped and update the exit code in the process table
        if proc and procces['state'] == 'T':
            procces['exit_code'] = proc.poll()
            return
    
        # check if the process should be running
        if procces['state'] == 'R':
            if not is_running(proc):
                logging.warning(f"Monitor Process: Process {process_name} found stopped.")
                procces['state'] = 'F'
                procces['exit_code'] = proc.poll()
                procces['proc'] = None

                if procces['restart']:
                    logging.info(f"Monitor Process: Restarting process {process_name}.")
                    self.start_process(process_name)
            else:
                #logging.info(f"Monitor Process: Process {process_name} is running.")
                procces['stdout'] = proc.stdout.read1().decode('utf-8')
                procces['stderr'] = proc.stderr.read1().decode('utf-8')
    
    def publish_host_info(self):
        
        #time
        current_time = time.time()
        time_diff = current_time - self.last_publish_time 
        self.last_publish_time = current_time
        
        # net io
        net_io = psutil.net_io_counters()
        net_tx = net_io.bytes_sent
        net_tx_diff = net_tx - self.last_net_tx
        self.last_net_tx = net_tx
        
        net_rx = net_io.bytes_recv
        net_rx_diff = net_rx - self.last_net_rx
        self.last_net_rx = net_rx
        
        sent_kbps = net_tx_diff/time_diff
        recv_kbps = net_rx_diff/time_diff
        

        # Gather system metrics
        cpu_usage = psutil.cpu_percent(interval=None) / 100.0  # Non-blocking
        
        uptime = int(time.time() - psutil.boot_time())  # Convert to milliseconds
        
        mem_total = psutil.virtual_memory().total
        mem_used = psutil.virtual_memory().used
        mem_free = psutil.virtual_memory().free
        mem_usage = psutil.virtual_memory().percent / 100.0
        

        # Create status message
        msg = host_info_t()
        msg.timestamp = int(time.time() * 1e6)
        msg.hostname = self.hostname
        msg.ip = get_ip()
        
        #cpu info
        msg.cpus = psutil.cpu_count()
        msg.cpu_usage = cpu_usage
        
        #memory info
        msg.mem_total = mem_total
        msg.mem_free = mem_free
        msg.mem_used = mem_used
        msg.mem_usage = mem_usage
        
        #network info
        msg.network_sent = sent_kbps/1024
        msg.network_recv = recv_kbps/1024
        
        #uptime
        msg.uptime = uptime

        # Send status message over LCM
        self.lc.publish(self.deputy_info_channel, msg.encode())
    
    def publish_host_procs(self):
        msg = host_procs_t()
        msg.timestamp = int(time.time() * 1e6)
        msg.hostname = self.hostname
        msg.procs = []
        msg.num_procs = 0
        
        for process_name, proc_info in self.processes.items():
            msg_proc = proc_info_t()
            msg_proc.name = process_name
                        
            proc = proc_info['proc']
            if proc and is_running(proc):
                
                msg_proc.cpu = proc.cpu_percent(interval=None) / 100.0  # Non-blocking
                mem_info = proc.memory_info()
                msg_proc.mem_rss = mem_info.rss // 1024  # Convert to KB
                msg_proc.mem_vms = mem_info.vms // 1024  # Convert to KB
                
                msg_proc.priority = proc.nice()
                msg_proc.pid = proc.pid
                msg_proc.ppid = proc.ppid()
                msg_proc.exit_code = -1  # Indicate that the process is still running
                msg_proc.errors = proc_info["errors"]
                msg_proc.status = proc.status()
                msg_proc.state = proc_info['state']
                msg_proc.group = proc_info['group']
                msg_proc.cmd = proc_info['cmd']
                msg_proc.realtime = proc_info['realtime']
                msg_proc.auto_restart = proc_info['restart']
                msg_proc.runtime = int(time.time() - proc.create_time())
        
            else:
                msg_proc.pid = -1
                msg_proc.exit_code = proc_info.get('exit_code', -1)
                msg_proc.errors = proc_info["errors"]
                msg_proc.status = proc_info['status']
                msg_proc.state = proc_info['state']
                msg_proc.group = proc_info['group']
                msg_proc.cmd = proc_info['cmd']
                

            msg.procs.append(msg_proc)
            msg.num_procs += 1
            proc_info["Errors"] = ""

        self.lc.publish(self.deputy_procs_channel, msg.encode())
        #logging.info(f"Proc Status Publish: Published status for process {process_name}")
        

    def publish_procs_outputs(self):
        for process_name, proc_info in self.processes.items():
            msg = proc_output_t()
            msg.timestamp = int(time.time() * 1e6)
            msg.name = process_name
            msg.hostname = self.hostname
            msg.stdout = proc_info['stdout'] + proc_info['stderr'] 
            self.lc.publish(self.proc_outputs_channel, msg.encode())
            
            proc_info['stdout'] = ''
            proc_info['stderr'] = ''
                    
    def run(self):
        logging.info("Deputy running.")
        while True:
            self.lc.handle_timeout(50)
            
            if self.monitor_timer.timeout():
                # Periodically check the status of processes
                for process_name in list(self.processes.keys()):
                    self.monitor_process(process_name)
            
            if self.output_timer.timeout():
                # Periodically publish process outputs
                self.publish_procs_outputs()

            if self.host_status_timer.timeout():
                # Periodically publish deputy status
                self.publish_host_info()
            
            if self.procs_status_timer.timeout():
                # Periodically gather and publish the status of individual processes
                self.publish_host_procs()


def daemonize():
    if os.fork() > 0:
        exit(0)
    os.setsid()
    if os.fork() > 0:
        exit(0)
    os.umask(0)
    os.chdir("/")
    os.close(0)
    os.close(1) 
    os.close(2)

if __name__ == "__main__":
    #daemonize()
    procman = Procman3()
    procman.run()
