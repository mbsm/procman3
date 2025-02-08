#!/usr/bin/env python3
import lcm
from procman3_messages import command_t
import socket
import time
    

def main():
    lc = lcm.LCM()
    msg = command_t()
    msg.name = "UKF Node"
    msg.group = "Perception"
    msg.sheriff = socket.gethostname()
    msg.deputy = socket.gethostname()
    msg.command = "create_process"
    msg.proc_command = "/home/mbustos/agv1/nodes/bin/ukf_node"
    msg.auto_restart = False
    msg.realtime = False
    lc.publish("procman3/commands", msg.encode())
    
    lc = lcm.LCM()
    msg = command_t()
    msg.name = "Obstacle Detection Node"
    msg.group = "Perception"
    msg.sheriff = socket.gethostname()
    msg.deputy = socket.gethostname()
    msg.command = "create_process"
    msg.proc_command = "/home/mbustos/agv1/nodes/bin/obstacle_detection_node"
    msg.auto_restart = False
    msg.realtime = False
    lc.publish("procman3/commands", msg.encode())
    
    
    msg = command_t()
    msg.name = "Motion Control Node"
    msg.group = "Control"
    msg.sheriff = socket.gethostname()
    msg.deputy = socket.gethostname()
    msg.command = "create_process"
    msg.proc_command = "/home/mbustos/agv1/nodes/bin/motion_controller_node"
    msg.auto_restart = True
    msg.realtime = False
    lc.publish("procman3/commands", msg.encode())
    
    
    time.sleep(5)
    
    msg = command_t()
    msg.name = "UKF Node"
    msg.deputy = socket.gethostname()
    msg.command = "start_process"
    lc.publish("procman3/commands", msg.encode())
    
    msg = command_t()
    msg.name = "Obstacle Detection Node"
    msg.deputy = socket.gethostname()
    msg.command = "start_process"
    lc.publish("procman3/commands", msg.encode())
    
    
    msg.name = "Motion Control Node"
    msg.deputy = socket.gethostname()
    msg.command = "start_process"
    lc.publish("procman3/commands", msg.encode())
    return 0

if __name__ == "__main__":
    exit(main())