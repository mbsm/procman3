#!/usr/bin/env python3
import lcm
import socket
from procman3_messages import command_t
    

def main():
    lc = lcm.LCM()
    msg = command_t()
    msg.name = "UKF Node"
    msg.command = "delete_process"
    msg.deputy = socket.gethostname()
    lc.publish("procman3/commands", msg.encode())
    
    msg = command_t()
    msg.name = "Motion Control Node"
    msg.command = "delete_process"
    msg.deputy = socket.gethostname()
    lc.publish("procman3/commands", msg.encode())

    return 0

if __name__ == "__main__":
    exit(main())