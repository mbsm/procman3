import os
import time
import lcm
import psutil
from subprocess import PIPE
import logging
import socket
import yaml
import fcntl
from procman3_messages import command_t, deputy_info_t, deputy_procs_t, proc_output_t, proc_info_t

# Configure logging
log_dir = "./log"
log_file = os.path.join(log_dir, "procman3.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    try:
        return proc.poll() is None
    except psutil.NoSuchProcess:
        return False



class Deputy:
    def __init__(self, config_file="config.yaml"):
        # Load configuration from YAML file
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        
        self.processes = {}
        
        self.lc = lcm.LCM()
        
        self.command_channel = config['command_channel']
        self.deputy_info_channel = config['deputy_info_channel']
        self.proc_outputs_channel = config['proc_outputs_channel']
        self.deputy_procs_channel = config['deputy_procs_channel']
        self.stop_timeout = config['stop_timeout']
        
        self.monitor_timer = Timer(config['monitor_interval'])
        self.output_timer = Timer(config['output_interval'])
        self.deputy_status_timer = Timer(config['deputy_status_interval'])
        self.procs_status_timer = Timer(config['procs_status_interval'])
        
        self.deputy_id = socket.gethostname()  # Use the hostname as the deputy's ID
        self.subscription = self.lc.subscribe(self.command_channel, self.command_handler)
        
        logging.info(f"Deputy initialized with channels: "
                     f"command_channel={self.command_channel}, "
                     f"deputy_info_channel={self.deputy_info_channel}, "
                     f"proc_outputs_channel={self.proc_outputs_channel}, "
                     f"deputy_procs_channel={self.deputy_procs_channel}")


    def command_handler(self, channel, data):
        msg = command_t.decode(data)
        if msg.deputy != self.deputy_id:
            logging.info(f"Command handler: Ignored command for deputy {msg.deputy}")
            return

        logging.info(f"Command handler: Received command: {msg.command} for process: {msg.proc_command}")
        group = msg.group
        
        if msg.command == "start_process":
            self.start_process(msg.name, msg.proc_command, msg.auto_restart, msg.realtime, group)
        elif msg.command == "stop_process":
            self.stop_process(msg.name)
        elif msg.command == "delete_process":
            self.delete_process(msg.name)
        else:
            logging.warning(f"Command handler: Unknown command: {msg.command} for process: {msg.proc_command}")


    def start_process(self, process_name, proc_command, restart_on_failure, realtime, group):
        
        if process_name in self.processes:
            proc_info = self.processes[process_name]
            proc = proc_info['proc']
            if is_running(proc):
                logging.info(f"Start Process: Process {process_name} is already running with PID {proc.pid}. Skipping start.")
                return
            else:
                logging.warning(f"Start Process: Process {process_name} is tracked but not running. Restarting process.")
    
        logging.info(f"Start Process: Starting process: {process_name} with command: {proc_command}")
        
        # create the process in the process table
        self.processes[process_name] = {'proc': None, 'cmd': proc_command,'restart': restart_on_failure,
                                        'exit_code': -1, 'group': group, 'errors': '', 'status': 'T',
                                        'stdout': '', 'stderr': ''} 
        
        try:
            proc = psutil.Popen([proc_command], stdout=PIPE, stderr=PIPE, text=True) # start the process text=True to get text output
            set_nonblocking(proc.stdout) # Set non-blocking mode for stdout
            set_nonblocking(proc.stderr) # Set non-blocking mode for stderr
            
            # update the process table with the new process
            self.processes[process_name]['proc'] = proc
            self.processes[process_name]['status'] = 'R'
            logging.info(f"Start Process: Started process: {process_name} with PID {proc.pid}")

            if realtime:
                try:
                    os.sched_setscheduler(proc.pid, os.SCHED_FIFO, os.sched_param(1))
                    logging.info(f"Start Process: Set real-time priority and FIFO scheduler for process: {process_name} with PID {proc.pid}")
                except PermissionError:
                    logging.error(f"Start Process: Failed to set real-time priority for process {process_name}: Permission denied.")
                    self.processes[process_name]['errors'] = f"Failed to set real-time priority for process {process_name}: Permission denied."
                except Exception as e:
                    logging.error(f"Start Process: Failed to set real-time priority for process {process_name}: {e}")
                    self.processes[process_name]['errors'] = str(e)

        except Exception as e:
            logging.error(f"Start Process: Failed to start process {process_name}: {e}")
            self.processes[process_name]['status'] = 'S'
            self.processes[process_name]['errors'] = str(e)
        
    def stop_process(self, process_name):
        if process_name in self.processes:
            proc_info = self.processes[process_name]
            proc = proc_info['proc']
            
            if(proc and proc_info['status'] == 'T'):
                logging.info(f"Stop Process: Process {process_name} is already stopped.")
                return
            
            try:
                proc.terminate()
                proc.wait(timeout=self.stop_timeout)  # Use the stop timeout variable
                logging.info(f"Stop Process: Gracefully stopped process: {process_name} with PID {proc.pid}")
                self.processes[process_name]['exit_code'] = proc.returncode
                self.processes[process_name]['status'] = 'T'
                
            except psutil.TimeoutExpired:
                proc.kill()  # Force kill
                logging.warning(f"Stop Process: Forcefully killed process: {process_name} with PID {proc.pid}")
                self.processes[process_name]['exit_code'] = proc.returncode
                self.processes[process_name]['status'] = 'T'
            
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
        if procces['status'] == 'T':
            procces['exit_code'] = proc.returncode
            return
    
        # check if the process should be running
        if procces['status'] == 'R':
            if not is_running(proc):
                logging.warning(f"Monitor Process: Process {process_name} found stopped.")
                procces['status'] = 'T'
                procces['exit_code'] = proc.returncode
                cmd = procces['cmd']
                if procces['restart']:
                    logging.info(f"Monitor Process: Restarting process {process_name}.")
                    self.start_process(process_name, cmd, procces['restart'], False, procces['group'])
            else:
                #logging.info(f"Monitor Process: Process {process_name} is running.")
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    procces['stdout'] += line
                
                while True:
                    line = proc.stderr.readline()
                    if not line:
                        break
                    procces['stderr'] += line
            
                    
    
    def publish_deputy_info(self):
        # Gather system metrics
        cpu_usage = psutil.cpu_percent(interval=None) / 100.0  # Non-blocking
        mem_usage = psutil.virtual_memory().percent / 100.0
        net_io = psutil.net_io_counters()
        network_sent = net_io.bytes_sent / 1024.0
        network_recv = net_io.bytes_recv / 1024.0
        uptime = int(time.time() - psutil.boot_time())  # Convert to milliseconds

        # Create status message
        msg = deputy_info_t()
        msg.timestamp = int(time.time() * 1e6)
        msg.deputy = self.deputy_id
        msg.ip = get_ip()
        msg.num_procs = len(self.processes)
        msg.cpu_usage = cpu_usage
        msg.mem_usage = mem_usage
        msg.network_sent = int(network_sent)
        msg.network_recv = int(network_recv)
        msg.uptime = uptime

        # Send status message over LCM
        self.lc.publish(self.deputy_info_channel, msg.encode())
        #logging.info("Deputy Status Publish: Sent status report.")
    
    def publish_deputy_procs(self):
        msg = deputy_procs_t()
        msg.timestamp = int(time.time() * 1e6)
        msg.deputy = self.deputy_id
        msg.procs = []
        msg.num_procs = 0
        
        for process_name, proc_info in self.processes.items():
            msg_proc = proc_info_t()
            msg_proc.name = process_name
                        
            proc = proc_info['proc']
            if proc and is_running(proc):
                msg_proc.cpu = proc.cpu_percent(interval=None) / 100.0  # Non-blocking
                mem_info = proc.memory_info()
                msg_proc.mem = mem_info.rss // 1024  # Convert to KB
                msg_proc.priority = proc.nice()
                msg_proc.pid = proc.pid
                msg_proc.exit_code = -1  # Indicate that the process is still running
                msg_proc.errors = proc_info["errors"]
                msg_proc.status = proc_info['status']
                msg_proc.group = proc_info['group']
                
        
            else:
                msg_proc.cpu = 0.0
                msg_proc.mem = 0
                msg_proc.priority = -1
                msg_proc.pid = -1
                msg_proc.exit_code = proc_info.get('exit_code', -1)
                msg_proc.errors = proc_info["errors"]
                msg_proc.status = proc_info['status']
                msg_proc.group = proc_info['group']
                

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
            msg.deputy = self.deputy_id
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

            if self.deputy_status_timer.timeout():
                # Periodically publish deputy status
                self.publish_deputy_info()
            
            if self.procs_status_timer.timeout():
                # Periodically gather and publish the status of individual processes
                self.publish_deputy_procs()


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
    deputy = Deputy()
    deputy.run()
