# procman3
Pure python based LCM based distributed process manager for robotics, inspired on libbot-procman

## Overview
Procman3 is a Python-based distributed process manager designed for robotics applications. It make use of the Lightweight Communications and Marshalling (LCM) library for inter-process communication, inspired by the libbot-procman project.

## Features
- Distributed process management
- LCM-based communication
- Easy integration with robotic systems

## How It Works
Procman3 uses LCM messages to manage and monitor processes across multiple machines. Each machine runs a local instance of procman3, and executes commands received through lcm and publish remote machine information, the information of each process the instace is managing and the stdout and stderr for each managed process.

## LCM Messages
Procman3 defines several LCM message types for communication:
- `command_t`: Used to send commands to remote hosts. Commands include create, start, stop, and delete processes. 
- `deputy_info_t`: Contains information about the remote host.
- `proc_output_t`: Contains the output of a process.
- `deputy_procs_t`: Contains information about the processes managed by a remote host procman3.

## LCM Channels
The default channels are: 
- `procman3/host_info`
- `procman3/proc_outputs`
- `procman3/host_procs`

## Usage
./procman3 -f=conf.yaml

if no file is especified the procman3 defaults to procman3.yaml as config file. 

## Getting Started
1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/procman3.git
    ```
2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```
3. Run the Procman3 manager:
    ```sh
    python procman3_manager.py
    ```

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License.
