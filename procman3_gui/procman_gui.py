import sys
import os
from PyQt5.QtWidgets import(QApplication, QMainWindow, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTextEdit, QTreeWidget, 
                            QTreeWidgetItem, QAction, QFileDialog, QInputDialog,  QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QSizePolicy, 
                            QSplitter, QMenu, QComboBox, QCheckBox)

from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from lcm_monitor import LCMHandler
import time
import yaml


def format_mem(Kbytes):
    if Kbytes < 1024:
        return f"{Kbytes:.1f} KB"
    elif Kbytes < 1024**2:
        return f"{Kbytes/1024:.1f} MB"
    else:
        return f"{Kbytes/1024**2:.1f} GB"


def format_percent(p):
    return f"{p*100:.1f}%"


def format_status(status, error):
    if status == 'R':
        return "Running"
    if status == "T":
        if error == '':
            return "Stoped (OK)"
        else:
            return "Stopped (Error)"


def format_time(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(seconds))


def format_traffic(kbps):
    if kbps < 1024:
        return f"{kbps:.1f} KB/s"
    else:
        return f"{kbps/1024:.1f} MB/s"
def format_state(state):
    if state == 'R':
        return "Running"
    elif state == 'T':
        return "Stopped"
    elif state == 'F':
        return "Fail"
    elif state == 'K':
        return "Killed"
    else:
        return "Unknown"

class BlankLineDumper(yaml.Dumper):
    def write_line_break(self, data=None):
        if len(self.indents) == 1:
            super().write_line_break(data)
        super().write_line_break(data)
#=====================================================================

class NodeStatus(QWidget):

    def __init__(self, name=None, parent=None):
        super(QWidget, self).__init__(parent)
        self.node_name = name

        d = 130
        frame_w = d
        frame_h = d
        label_w = d-20

        self.status = 1  # 1 running, 0 stoped
        self.mem_usage = 0
        self.cpu_usage = 0
  

        self.setStyleSheet("font: 10px")
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setLineWidth(1)
        self.frame.setFixedWidth(frame_w)
        self.frame.setFixedHeight(frame_h)

        self.name = QLabel(self.node_name)
        self.name.setFixedWidth(label_w)
        self.name.setStyleSheet("font: bold 12px")


        self.state = QLabel()
        self.state.setFixedWidth(label_w)
        self.frec = QLabel()
        self.frec.setFixedWidth(label_w)
        self.host = QLabel()
        self.mem = QLabel()
        self.cpu = QLabel()

        frame_layout = QVBoxLayout()
        frame_layout.addWidget(self.name)
        frame_layout.addWidget(self.state, alignment=Qt.AlignLeft)
        frame_layout.addWidget(self.host, alignment=Qt.AlignLeft)
        frame_layout.addWidget(self.mem, alignment=Qt.AlignLeft)
        frame_layout.addWidget(self.cpu, alignment=Qt.AlignLeft)
        frame_layout.setAlignment(Qt.AlignCenter)

        self.frame.setLayout(frame_layout)
        widget_layout = QHBoxLayout()
        widget_layout.addWidget(self.frame)
        widget_layout.setAlignment(Qt.AlignCenter)
        self.setLayout(widget_layout)
        self.last_update = time.time()
        
        # timer to check if the node is still alive onece per second
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_status)
        self.timer.start(1000)


    def check_status(self):
        now = time.time()
        if now - self.last_update > 5:
            self.status = 0
            self.mem_usage = 0
            self.cpu_usage = 0
            self.textUpdate()
        else:
            self.textUpdate()

    def update(self):
        self.textUpdate()
        self.last_update = time.time()
    
    def textUpdate(self):
        status_text = ['Stoped', 'Running']
        status_color = ["color: red", "color: green"]

        self.name.setText(self.node_name)
        self.host.setText('Host: {}'.format(self.host_name))
        if self.mem_usage < 1024:
            self.mem.setText('Mem usage: {:.1f} KB'.format(self.mem_usage))
        elif self.mem_usage > 1024:
            self.mem.setText('Mem usage: {:.1f} MB'.format(self.mem_usage/1024))
        
        self.cpu.setText('Cpu usage: {:.1f} %'.format(self.cpu_usage))
        self.state.setText(status_text[self.status])
        self.state.setStyleSheet(status_color[self.status])

    def set_node_name(self, name):
        self.node_name = name

    def set_status(self, status):
        self.status = status

    def set_frecuency(self, frec):
        self.frecuency = frec

    def set_mem_usage(self, mem):
        self.mem_usage = mem

    def set_cpu_usage(self, cpu):
        self.cpu_usage = cpu

    def set_host_name(self, host):
        self.host_name = host



class NodeStatusDisplay(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent)
        self.groups = {}
        self.nodes = {}
        widget_layout = QVBoxLayout()     
        self.setLayout(widget_layout)

    def newGroup(self, group):
        frame = QGroupBox()
        frame.setTitle(group)
        self.groups[group] = frame
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignLeft)
        frame.setLayout(layout)
        self.layout().addWidget(frame)
    
    def addNodetoGroup(self, group, node):
        self.nodes[node] = NodeStatus(node)
        self.groups[group].layout().addWidget(self.nodes[node], alignment=Qt.AlignLeft)
    
    def updateNode(self, node, group, host, cpu, mem, frec, status):
        # check if node and group exist, if not create them and add the node, then update the node
        if group not in self.groups:
            self.newGroup(group)
        if node not in self.nodes:
            self.addNodetoGroup(group, node)
                    
        self.nodes[node].set_status(status)
        self.nodes[node].set_mem_usage(mem)
        self.nodes[node].set_cpu_usage(cpu)
        self.nodes[node].set_host_name(host)
        self.nodes[node].update()

#=====================================================================

class PropertiesDialog(QDialog):
    def __init__(self, refresh_rate, udmp, host_info_channel, host_procs_channel, proc_output_channel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Properties")
        self.setFixedSize(500, 200)

        self.refreshRateInput = QLineEdit(str(refresh_rate))
        self.udmpInput = QLineEdit(udmp)
        self.hostInfoChannelInput = QLineEdit(host_info_channel)
        self.hostProcsChannelInput = QLineEdit(host_procs_channel)
        self.procOutputChannelInput = QLineEdit(proc_output_channel)

        formLayout = QFormLayout()
        formLayout.addRow("Refresh Rate (s):", self.refreshRateInput)
        formLayout.addRow("UDMP for LCM:", self.udmpInput)
        formLayout.addRow("Host Info Channel:", self.hostInfoChannelInput)
        formLayout.addRow("Host Procs Channel:", self.hostProcsChannelInput)
        formLayout.addRow("Proc Output Channel:", self.procOutputChannelInput)
        
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(formLayout)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)

    def getValues(self):
        return float(self.refreshRateInput.text()), self.udmpInput.text(), self.hostInfoChannelInput.text(), self.hostProcsChannelInput.text(), self.procOutputChannelInput.text()

class EditProcessDialog(QDialog):
    def __init__(self, process_name, host_name, group, cmd, auto_restart, realtime, hosts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Process")
        self.setFixedSize(400, 300)

        self.processNameInput = QLineEdit(process_name)
        
        self.hostNameInput = QComboBox()
        self.hostNameInput.addItems(hosts)
        self.hostNameInput.setCurrentText(host_name)
        self.groupInput = QLineEdit(group)        
        self.cmdInput = QLineEdit(cmd)
        self.autoRestartInput = QCheckBox()
        self.autoRestartInput.setChecked(auto_restart)
        self.realtimeInput = QCheckBox()
        self.realtimeInput.setChecked(realtime)

        formLayout = QFormLayout()
        formLayout.addRow("Process Name:", self.processNameInput)
        formLayout.addRow("Host Name:", self.hostNameInput)
        formLayout.addRow("Group:", self.groupInput)
        formLayout.addRow("Command:", self.cmdInput)
        formLayout.addRow("Auto Restart:", self.autoRestartInput)
        formLayout.addRow("Realtime:", self.realtimeInput)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(formLayout)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)

    def getValues(self):
        return (self.processNameInput.text(), self.hostNameInput.currentText(), self.groupInput.text(), self.cmdInput.text(), 
                self.autoRestartInput.isChecked(), self.realtimeInput.isChecked())
        
        
class AddProcessDialog(QDialog):
    def __init__(self, hosts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Process")
        self.setFixedSize(400, 300)

        self.processNameInput = QLineEdit("")
        
        self.hostNameInput = QComboBox()
        self.hostNameInput.addItems(hosts)
        self.hostNameInput.setCurrentText("")
        self.groupInput = QLineEdit("")        
        self.cmdInput = QLineEdit("")
        self.autoRestartInput = QCheckBox()
        self.autoRestartInput.setChecked(False)
        self.realtimeInput = QCheckBox()
        self.realtimeInput.setChecked(False)

        formLayout = QFormLayout()
        formLayout.addRow("Process Name:", self.processNameInput)
        formLayout.addRow("Host Name:", self.hostNameInput)
        formLayout.addRow("Group:", self.groupInput)
        formLayout.addRow("Command:", self.cmdInput)
        formLayout.addRow("Auto Restart:", self.autoRestartInput)
        formLayout.addRow("Realtime:", self.realtimeInput)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(formLayout)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)

    def getValues(self):
        return (self.processNameInput.text(), self.hostNameInput.currentText(), self.groupInput.text(), self.cmdInput.text(), 
                self.autoRestartInput.isChecked(), self.realtimeInput.isChecked())

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        #parameters:
        self.udpm ="udpm://239.255.76.67:7667?ttl=1" # LCM multicast address
        self.refresh_rate = 0.5       # refresh rate in seconds 
        self.host_info_channel = "procman3/host_info"
        self.host_procs_channel = "procman3/host_procs"
        self.proc_output_channel = "procman3/proc_outputs"
        
        #setup the GUI 
        self.setupUi(self)
        
        #setup the LCM handler
        host_name = os.environ.get("HOSTNAME")
        self.lcm_handler = LCMHandler(self.udpm, host_name, self.host_info_channel, self.host_procs_channel, self.proc_output_channel)  
        
        self.lcm_handler.host_info_signal.connect(self.set_hosts)
        self.lcm_handler.process_info_signal.connect(self.set_processes)
        self.lcm_handler.output_signal.connect(self.set_outputs)
        self.lcm_handler.start()

        #initialize the data structures
        self.hosts = {}
        self.processes = {}
        self.outputs = {}
        
        # Connect the context menu event to the process tree
        self.processTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.processTree.customContextMenuRequested.connect(self.open_context_menu)

        # timer to update the GUI periodically
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(int(self.refresh_rate * 1000))
        
        

    def set_hosts(self, hosts):
        self.hosts = hosts

    def set_processes(self, processes):
        self.processes = processes

    def set_outputs(self, outputs):
        self.outputs = outputs
             
    def open_context_menu(self, position):
        indexes = self.processTree.selectedIndexes()
        if indexes:
            selected_item = self.processTree.itemAt(position)
            if selected_item:
                menu = QMenu()

                start_action = QAction("Start", self)
                stop_action = QAction("Stop", self)
                delete_action = QAction("Delete", self)
                edit_action = QAction("Edit", self)
                add_action = QAction("Add", self)

                selected_process_name = selected_item.text(1)
                selected_group = selected_item.text(0)
                
                if selected_process_name != '': # selected item is a process
                    process_info = self.processes[selected_process_name]
                    selected_host_name = process_info["hostname"]
                    selected_group = process_info["group"]  
                    selected_cmd = process_info["cmd"]
                    selected_auto_restart = process_info["auto_restart"]
                    selected_realtime = process_info["realtime"]

                    start_action.triggered.connect(lambda: self.lcm_handler.start_process(selected_host_name, selected_process_name))
                    stop_action.triggered.connect(lambda: self.lcm_handler.stop_process(selected_host_name, selected_process_name))
                    delete_action.triggered.connect(lambda: self.lcm_handler.delete_process(selected_host_name, selected_process_name))
                    edit_action.triggered.connect(lambda: self.edit_process(selected_process_name, selected_host_name, selected_group, selected_cmd, selected_auto_restart, selected_realtime))
                    
                    menu.addAction(start_action)
                    menu.addAction(stop_action)
                    menu.addAction(delete_action)
                    menu.addAction(edit_action)

                else: #selected item is a group
                    start_action.triggered.connect(lambda: self.start_group(selected_group))
                    stop_action.triggered.connect(lambda: self.stop_group(selected_group))
                    add_action.triggered.connect(self.add_process)
                    
                    menu.addAction(start_action)
                    menu.addAction(stop_action)
                    menu.addAction(add_action)
                    
                menu.exec_(self.processTree.viewport().mapToGlobal(position))

    def edit_process(self, process_name, host_name, group, cmd, auto_restart, realtime):
        dialog = EditProcessDialog(process_name, host_name, group, cmd, auto_restart, realtime, self.hosts.keys(), self)
        if dialog.exec_() == QDialog.Accepted:
            new_process_name, new_host_name, new_group, new_cmd, new_auto_restart, new_realtime = dialog.getValues()
            self.lcm_handler.stop_process(host_name, process_name)
            self.lcm_handler.delete_process(host_name, process_name)
            self.lcm_handler.create_process(new_host_name, new_group, new_process_name, new_auto_restart, new_cmd, new_realtime)
            
    def add_process(self):
        dialog = AddProcessDialog(self.hosts.keys(), self)
        if dialog.exec_() == QDialog.Accepted:
            process_name, host_name, group, cmd, auto_restart, realtime = dialog.getValues()
            self.lcm_handler.create_process(host_name, group, process_name, auto_restart, cmd, realtime)

    def start_group(self, group):
        for process_name, process_info in self.processes.items():
            if process_info["group"] == group:
                self.lcm_handler.start_process(process_info["hostname"], process_name)
    
    def stop_group(self, group):
        for process_name, process_info in self.processes.items():
            if process_info["group"] == group:
                self.lcm_handler.stop_process(process_info["hostname"], process_name)
                

    def update_gui(self):
        self.update_host_table(self.hosts)
        self.updateProcessTree(self.processes)
        self.update_output_text(self.outputs)

    def update_host_table(self, hosts):
        self.hostTable.setRowCount(len(hosts))
        for row, (name, info) in enumerate(hosts.items()):
            now = time.time()  
            
            #set name
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.hostTable.setItem(row, 0, name_item)
            
            #set ip
            ip_item = QTableWidgetItem(info["ip"])
            ip_item.setTextAlignment(Qt.AlignCenter)
            self.hostTable.setItem(row, 1, ip_item)
            
            #set host total cpu usage
            cpu_item = QTableWidgetItem(format_percent(info["cpu_usage"]))
            cpu_item.setTextAlignment(Qt.AlignCenter)
            if(info["cpu_usage"] > 0.8):
                cpu_item.setBackground(QColor("red"))
            
            if info["cpu_usage"] > 0.5:
                cpu_item.setForeground(QColor("yellow"))

            self.hostTable.setItem(row, 2, cpu_item)
            
            #set host total memory usage
            mem_item = QTableWidgetItem(format_percent(info["mem_used"]))
            mem_item.setTextAlignment(Qt.AlignCenter)
            self.hostTable.setItem(row, 3, mem_item)
            
            #set host network traffic
            tx_item = QTableWidgetItem(format_traffic(info["net_tx"]))
            tx_item.setTextAlignment(Qt.AlignCenter)
            self.hostTable.setItem(row, 4, tx_item)
            
            rx_item = QTableWidgetItem(format_traffic(info["net_rx"]))
            rx_item.setTextAlignment(Qt.AlignCenter)
            self.hostTable.setItem(row, 5, rx_item)
            
            #set seconds since last time we got a report
            dt = now - info["last_update"]
            last_update_item = QTableWidgetItem(f"{dt:.1f}")
            last_update_item.setTextAlignment(Qt.AlignCenter)
            
            if dt > 5:
                last_update_item.setBackground(QColor("red"))
                
            self.hostTable.setItem(row, 6, last_update_item)
            

        self.hostTable.resizeColumnsToContents()

    def updateProcessTree(self, processes):
        # create a dictionary that reference the processTree items by group name    
        groups = {}
        for i in range(self.processTree.topLevelItemCount()):
            group_item = self.processTree.topLevelItem(i)
            groups[group_item.text(0)] = group_item

        # Track which groups and processes are still present
        present_groups = set()
        present_processes = set()
        group_cpu_usage = {}
        group_mem_usage = {}
        group_states = {}
        group_runtime = {}

        for process_name, process_info in processes.items():
            group = process_info["group"]
            present_groups.add(group)
            present_processes.add(process_name)

            if group not in groups:
                groups[group] = QTreeWidgetItem(self.processTree, [group])
            group_item = groups[group]

            # Initialize or update the CPU and memory usage for the group
            if group not in group_cpu_usage:
                group_cpu_usage[group] = 0
            if group not in group_mem_usage:
                group_mem_usage[group] = 0
            if group not in group_states:
                group_states[group] = set()
            if group not in group_runtime:
                group_runtime[group] = 1e10 #some large number

            group_cpu_usage[group] += process_info["cpu"]
            group_mem_usage[group] += process_info["mem_rss"]
            group_states[group].add(process_info["state"])
            group_runtime[group] = min(group_runtime[group], process_info["runtime"])

            process_item = None
            for i in range(group_item.childCount()):
                child = group_item.child(i)
                if child.text(1) == process_name:
                    process_item = child
                    break

            if process_item is None:
                process_item = QTreeWidgetItem(
                    group_item,
                    [
                        "",
                        process_name,
                        process_info["cmd"],
                        format_state(process_info['state']),
                        process_info["hostname"],
                        format_percent(process_info["cpu"]),
                        format_mem(process_info["mem_rss"]),
                        str(process_info["pid"]),
                        str(process_info["priority"]),
                        format_time(process_info["runtime"]),
                        str(process_info["errors"][:30]),
                    ],
                )
                group_item.addChild(process_item)
            else:
                process_item.setText(1, process_name)
                process_item.setText(2, process_info["cmd"])
                process_item.setText(3, format_state(process_info["state"]))
                process_item.setText(4, process_info["hostname"])
                process_item.setText(5, format_percent(process_info["cpu"]))
                process_item.setText(6, format_mem(process_info["mem_rss"]))
                process_item.setText(7, str(process_info["pid"]))
                process_item.setText(8, str(process_info["priority"]))
                process_item.setText(9, format_time(process_info["runtime"]))
                process_item.setText(10, str(process_info["errors"][:30]))

            process_item.setTextAlignment(1, Qt.AlignLeft)
            process_item.setTextAlignment(2, Qt.AlignLeft)
            process_item.setTextAlignment(3, Qt.AlignCenter)
            process_item.setTextAlignment(4, Qt.AlignLeft)
            process_item.setTextAlignment(5, Qt.AlignRight)
            process_item.setTextAlignment(6, Qt.AlignRight)
            process_item.setTextAlignment(7, Qt.AlignCenter)
            process_item.setTextAlignment(8, Qt.AlignCenter)
            process_item.setTextAlignment(9, Qt.AlignCenter)
            process_item.setTextAlignment(10, Qt.AlignLeft)

            if process_info["state"] == "K" or process_info["status"] == "F":
                process_item.setBackground(3, QColor("red"))

            elif process_info["state"] == "R":
                process_item.setBackground(3, QColor("Green"))
            elif process_info["state"] == "T":
                process_item.setBackground(3, QColor('#333333'))
            else:
                process_item.setBackground(3, QColor("Yellow"))
                process_item.setForeground(3, QColor("Black"))
                
                

        ## Update group items with the total CPU and memory usage
        for group, group_item in groups.items():
            if group in group_cpu_usage and group in group_mem_usage:
                group_item.setText(5, format_percent(group_cpu_usage[group]))
                group_item.setText(6, format_mem(group_mem_usage[group]))
                group_item.setText(9, format_time(group_runtime[group]))
                
                if all(state == 'R' for state in group_states[group]):
                    group_item.setText(3, 'Running')
                    group_item.setBackground(3, QColor("Green"))
                elif all(state == 'T' for state in group_states[group]):
                    group_item.setText(3, 'Stopped')
                       #self.setStyleSheet('background-color: #333333; color: #d3d3d3;')
                    group_item.setBackground(3, QColor('#333333'))
                elif any(state == 'F' for state in group_states[group]):
                    group_item.setText(3, 'Error')
                    group_item.setBackground(3, QColor("Red"))
                elif any(state == 'K' for state in group_states[group]):
                    group_item.setText(3, 'Error')
                    group_item.setBackground(3, QColor("Red"))
                else:
                    group_item.setText(3, 'Mixed')
                    group_item.setBackground(3, QColor("Yellow"))
                    group_item.setForeground(3, QColor("Black"))

            group_item.setTextAlignment(1, Qt.AlignLeft)
            group_item.setTextAlignment(2, Qt.AlignLeft)
            group_item.setTextAlignment(3, Qt.AlignCenter)
            group_item.setTextAlignment(4, Qt.AlignLeft)
            group_item.setTextAlignment(5, Qt.AlignRight)
            group_item.setTextAlignment(6, Qt.AlignRight)
            group_item.setTextAlignment(7, Qt.AlignCenter)
            group_item.setTextAlignment(8, Qt.AlignCenter)
            group_item.setTextAlignment(9, Qt.AlignCenter)
            group_item.setTextAlignment(10, Qt.AlignLeft)


        # Remove groups and processes that are no longer present
        for group_name, group_item in groups.items():
            if group_name not in present_groups:
                index = self.processTree.indexOfTopLevelItem(group_item)
                self.processTree.takeTopLevelItem(index)
            else:
                for i in range(group_item.childCount() - 1, -1, -1):
                    child = group_item.child(i)
                    if child.text(1) not in present_processes:
                        group_item.removeChild(child)

        for i in range(9):
            self.processTree.resizeColumnToContents(i)

        
    def update_output_text(self, outputs):
        # get the selected row in the process table
        item = self.processTree.currentItem()

        if item is None:
            return

        # get the name of the selected process
        selected_process_name = item.text(1)

        # check that process name is a key in  outputs
        if selected_process_name not in outputs:
            return

        # get the output of the selected process in the outputText
        self.outputText.clear()
        self.outputText.append(
            f"=== {selected_process_name} ===\n{outputs[selected_process_name]['stdout']}\n"
        )
                

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1800, 600)
        self.setStyleSheet('background-color: #333333; color: #d3d3d3;')
        self.createMenuBar()

        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)

        # Create the main horizontal layout
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")

        # Create the left vertical layout
        self.leftVerticalLayout = QVBoxLayout()
        self.leftVerticalLayout.setObjectName("leftVerticalLayout")

        # Create the process tree and add it to the left vertical layout
        self.processTree = QTreeWidget(self.centralwidget)
        self.processTree.setObjectName("processTree")
        self.processTree.setColumnCount(10)  # Set the number of columns
        self.processTree.setHeaderLabels(
            ["Group", "Name", "Command", "State", "Host", "CPU", "Mem", "Pid", "Priority", "Runtime", "Errors"])  # Set column names

        self.processTree.setFixedWidth(1300)
        self.leftVerticalLayout.addWidget(self.processTree)

        # Create the host table and add it to the left vertical layout
        self.hostTable = QTableWidget(self.centralwidget)
        self.hostTable.setObjectName("hostTable")
        self.hostTable.setColumnCount(7)  # Set the number of columns
        self.hostTable.setHorizontalHeaderLabels(["Host", "IP", "CPU", "Mem", "Net Send", "Net Recv", "Last Update"])  # Set column names
        self.hostTable.verticalHeader().setVisible(False)  # Hide the vertical header
        self.hostTable.resizeColumnsToContents()
        self.leftVerticalLayout.addWidget(self.hostTable)

        # Add the left vertical layout to the main horizontal layout
        self.horizontalLayout.addLayout(self.leftVerticalLayout)

        # Create the output text and add it to the main horizontal layout
        self.outputText = QTextEdit(self.centralwidget)
        self.outputText.setObjectName("outputText")
        self.horizontalLayout.addWidget(self.outputText)

        self.setWindowTitle("Procman GUI")
        
    def createMenuBar(self):
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('File')

        loadAction = QAction('Load', self)
        loadAction.triggered.connect(self.loadFile)
        fileMenu.addAction(loadAction)

        saveAction = QAction('Save', self)
        saveAction.triggered.connect(self.saveFile)
        fileMenu.addAction(saveAction)

        propertiesAction = QAction('Properties', self)
        propertiesAction.triggered.connect(self.showProperties)
        fileMenu.addAction(propertiesAction)

        exitAction = QAction('Exit', self)
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)

    def loadFile(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Load Process Information", "", "All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            # Load the process information from the file
            with open(fileName, 'r') as file:
                data = yaml.load(file, Loader=yaml.FullLoader)
                refresh_rate = data['ProcmanGuiParameters']['refresh_rate']
                udpm = data['ProcmanGuiParameters']['udpm']
                self.setProperties(self.refresh_rate, self.udpm)
                                
                # Add the processes from the file
                for process in data['Processes']:
                    self.lcm_handler.create_process(process['host'], process['group'], process['name'], process['auto_restart'], process['cmd'], process["realtime"])
                    
                # Set the LCM channels from the file 
                # check if the file has the LCMChannels key
                if 'LCMChannels' in data:
                    host_info_channel = data['LCMChannels']['host_info_channel']
                    host_procs_channel = data['LCMChannels']['host_procs_channel']
                    proc_output_channel = data['LCMChannels']['proc_output_channel']
                    self.setLCMChannels(host_info_channel, host_procs_channel, proc_output_channel)
                
                # Set the properties from the file
                if 'ProcmanGuiParameters' in data:
                    refresh_rate = data['ProcmanGuiParameters']['refresh_rate']
                    udpm = data['ProcmanGuiParameters']['udpm']
                    self.setProperties(refresh_rate, udpm)
                    

    def saveFile(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Process Information", "", "YAML Files (*.yaml);;All Files (*)", options=options)
        
        if fileName:
            data ={}
            data['ProcmanGuiParameters'] = {}
            data['ProcmanGuiParameters']['refresh_rate'] = self.refresh_rate
            data['ProcmanGuiParameters']['udpm'] = self.udpm
            data['Processes'] = []
            
            # Collect process information from self.process
            for name, process in self.processes.items():
                process_info = {
                    'name': name,
                    'host': process['host'],
                    'cmd': process['cmd'],
                    'group': process['group'],
                    'auto_restart': process['auto_restart'],
                    'realtime': process['realtime']
                }
                data['Processes'].append(process_info)
            
            data['LCMChannels'] = {}
            data['LCMChannels']['host_info_channel'] = self.host_info_channel
            data['LCMChannels']['host_procs_channel'] = self.host_procs_channel
            data['LCMChannels']['proc_output_channel'] = self.proc_output_channel

            # Save data to YAML file
            with open(fileName, 'w') as file:
                yaml.dump(data, file,Dumper=BlankLineDumper)
                
                
    def showProperties(self):
        dialog = PropertiesDialog(self.refresh_rate, self.udpm, self.host_info_channel, self.host_procs_channel, self.proc_output_channel)
        if dialog.exec_() == QDialog.Accepted:
            refresh_rate, udpm, host_info_channel, host_proc_channel, proc_output_channel = dialog.getValues()
            self.setProperties(refresh_rate, udpm)
            self.setLCMChannels(host_info_channel, host_proc_channel, proc_output_channel)
    
            
    def setProperties(self, refresh_rate, udpm):
         # stop the timer and start it with the new refresh rate
        self.refresh_rate = refresh_rate
        self.udpm = udpm
        self.timer.stop()
        self.timer.start(int(self.refresh_rate * 1000))
            
        # change the udpm in the lcm handler
        self.lcm_handler.change_udpm(self.udpm)
    
    def setLCMChannels(self, host_info_channel, host_proc_channel, proc_output_channel):
        self.host_info_channel = host_info_channel
        self.host_procs_channel = host_proc_channel
        self.proc_output_channel = proc_output_channel
        self.lcm_handler.change_channels(self.host_info_channel, self.host_procs_channel, self.proc_output_channel)
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
