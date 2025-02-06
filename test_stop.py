#!/usr/bin/env python3
import lcm
import socket
from procman3_messages import command_t
    

def main():
    lc = lcm.LCM()
    msg = command_t()
    msg.name = "UKF Node"
    msg.group = "Perception"
    msg.sheriff = socket.gethostname()
    msg.deputy = socket.gethostname()
    msg.command = "stop_process"
    msg.proc_command = "/home/mbustos/agv1/nodes/bin/ukf_node"
    msg.auto_restart = False
    msg.realtime = False
    lc.publish("procman3/commands", msg.encode())
    return 0

if __name__ == "__main__":
    exit(main())