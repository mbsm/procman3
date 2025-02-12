import sys
import os
from PyQt5.QtWidgets import( 
                            QApplication, 
                            QMainWindow, 
                            QTableWidgetItem, 
                            QWidget, 
                            QVBoxLayout, 
                            QHBoxLayout, 
                            QTableWidget, 
                            QTextEdit, 
                            QTreeWidget, 
                            QTreeWidgetItem, 
                            QAction, 
                            QFileDialog, 
                            QInputDialog, 
                            QDialog, 
                            QLineEdit, 
                            QFormLayout, 
                            QDialogButtonBox, 
                            QSizePolicy, 
                            QSplitter, 
                            QMenu)

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

class BlankLineDumper(yaml.Dumper):
    def write_line_break(self, data=None):
        if len(self.indents) == 1:
            super().write_line_break(data)
        super().write_line_break(data)


class PropertiesDialog(QDialog):
    def __init__(self, refresh_rate, udmp, deputy_info_channel, deputy_procs_channel, proc_output_channel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Properties")
        self.setFixedSize(500, 200)

        self.refreshRateInput = QLineEdit(str(refresh_rate))
        self.udmpInput = QLineEdit(udmp)
        self.deputyInfoChannelInput = QLineEdit(deputy_info_channel)
        self.deputyProcsChannelInput = QLineEdit(deputy_procs_channel)
        self.procOutputChannelInput = QLineEdit(proc_output_channel)

        formLayout = QFormLayout()
        formLayout.addRow("Refresh Rate (s):", self.refreshRateInput)
        formLayout.addRow("UDMP for LCM:", self.udmpInput)
        formLayout.addRow("Deputy Info Channel:", self.deputyInfoChannelInput)
        formLayout.addRow("Deputy Procs Channel:", self.deputyProcsChannelInput)
        formLayout.addRow("Proc Output Channel:", self.procOutputChannelInput)
        
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(formLayout)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)

    def getValues(self):
        return float(self.refreshRateInput.text()), self.udmpInput.text(), self.deputyInfoChannelInput.text(), self.deputyProcsChannelInput.text(), self.procOutputChannelInput.text()


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        #parameters:
        self.udpm ="udpm://239.255.76.67:7667?ttl=1" # LCM multicast address
        self.refresh_rate = 0.5       # refresh rate in seconds 
        self.deputy_info_channel = "procman3/deputy_info"
        self.deputy_procs_channel = "procman3/deputy_procs"
        self.proc_output_channel = "procman3/proc_outputs"
        
        #setup the GUI 
        self.setupUi(self)
        
        #setup the LCM handler
        host_name = os.environ.get("HOSTNAME")
        self.lcm_handler = LCMHandler(self.udpm, host_name, self.deputy_info_channel, self.deputy_procs_channel, self.proc_output_channel)  
        
        self.lcm_handler.deputy_info_signal.connect(self.set_deputies)
        self.lcm_handler.process_info_signal.connect(self.set_processes)
        self.lcm_handler.output_signal.connect(self.set_outputs)
        self.lcm_handler.start()

        #initialize the data structures
        self.deputies = {}
        self.processes = {}
        self.outputs = {}
        
        # Connect the context menu event to the process tree
        self.processTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.processTree.customContextMenuRequested.connect(self.open_context_menu)

        # timer to update the GUI periodically
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(int(self.refresh_rate * 1000))
        
        

    def set_deputies(self, deputies):
        self.deputies = deputies

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

                selected_process_name = selected_item.text(1)
                selected_deputy_name = selected_item.text(2)

                start_action.triggered.connect(lambda: self.lcm_handler.start_process(selected_deputy_name, selected_process_name))
                stop_action.triggered.connect(lambda: self.lcm_handler.stop_process(selected_deputy_name, selected_process_name))
                delete_action.triggered.connect(lambda: self.lcm_handler.delete_process(selected_deputy_name, selected_process_name))

                menu.addAction(start_action)
                menu.addAction(stop_action)
                menu.addAction(delete_action)

                menu.exec_(self.processTree.viewport().mapToGlobal(position))

    def update_gui(self):
        self.update_deputy_table(self.deputies)
        self.updateProcessTree(self.processes)
        self.update_output_text(self.outputs)

    def update_deputy_table(self, deputies):
        self.deputyTable.setRowCount(len(deputies))
        for row, (name, info) in enumerate(deputies.items()):
            now = time.time()  
            
            #set name
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.deputyTable.setItem(row, 0, name_item)
            
            #set ip
            ip_item = QTableWidgetItem(info["ip"])
            ip_item.setTextAlignment(Qt.AlignCenter)
            self.deputyTable.setItem(row, 1, ip_item)
            
            #set num process managing
            num_procs_item = QTableWidgetItem(str(info["num_procs"]))
            num_procs_item.setTextAlignment(Qt.AlignCenter)
            self.deputyTable.setItem(row, 2, num_procs_item)
            
            #set deputy total cpu usage
            cpu_item = QTableWidgetItem(format_percent(info["cpu"]))
            cpu_item.setTextAlignment(Qt.AlignCenter)
            if(info["cpu"] > 0.8):
                cpu_item.setBackground(QColor("red"))
            
            if info["cpu"] > 0.5:
                cpu_item.setForeground(QColor("yellow"))

            self.deputyTable.setItem(row, 3, cpu_item)
            
            #set deputy total memory usage
            mem_item = QTableWidgetItem(format_percent(info["mem"]))
            mem_item.setTextAlignment(Qt.AlignCenter)
            self.deputyTable.setItem(row, 4, mem_item)
            
            #set deputy network traffic
            tx_item = QTableWidgetItem(format_traffic(info["net_tx"]))
            tx_item.setTextAlignment(Qt.AlignCenter)
            self.deputyTable.setItem(row, 5, tx_item)
            
            rx_item = QTableWidgetItem(format_traffic(info["net_rx"]))
            rx_item.setTextAlignment(Qt.AlignCenter)
            self.deputyTable.setItem(row, 6, rx_item)
            
            #set seconds since last time we got a report
            dt = now - info["last_update"]
            last_update_item = QTableWidgetItem(f"{dt:.1f}")
            last_update_item.setTextAlignment(Qt.AlignCenter)
            
            if dt > 5:
                last_update_item.setBackground(QColor("red"))
                
            self.deputyTable.setItem(row, 7, last_update_item)
            

        self.deputyTable.resizeColumnsToContents()

    def updateProcessTree(self, processes):
        groups = {}
        for i in range(self.processTree.topLevelItemCount()):
            group_item = self.processTree.topLevelItem(i)
            groups[group_item.text(0)] = group_item

        # Track which groups and processes are still present
        present_groups = set()
        present_processes = set()

        for process_name, process_info in processes.items():
            group = process_info["group"]
            present_groups.add(group)
            present_processes.add(process_name)

            if group not in groups:
                groups[group] = QTreeWidgetItem(self.processTree, [group])
            group_item = groups[group]

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
                        process_info["deputy"],
                        process_info["cmd"],
                        format_status(process_info["status"], process_info['errors']),
                        format_percent(process_info["cpu"]),
                        format_mem(process_info["mem"]),
                        str(process_info["pid"]),
                        str(process_info["priority"]),
                        format_time(process_info["runtime"]),
                        str(process_info["errors"][:30]),
                    ],
                )
                group_item.addChild(process_item)
            else:
                process_item.setText(1, process_name)
                process_item.setText(2, process_info["deputy"])
                process_item.setText(3, format_status(process_info["status"], process_info['errors']))
                process_item.setText(4, process_info["cmd"])
                process_item.setText(5, format_percent(process_info["cpu"]))
                process_item.setText(6, format_mem(process_info["mem"]))
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
            
            
            if process_info["status"] == "T" and process_info["errors"] != "":
                process_item.setBackground(3, QColor("red"))
                
            if process_info["status"] == "R":
                process_item.setBackground(3, QColor("Green"))
                
            if process_info["cpu"] > 0.8:
                process_item.setForeground(4, QColor("red"))
            else:
                process_item.setForeground(4, QColor("black"))
            

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
        MainWindow.resize(1500, 600)
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
            ["Group", "Name", "Deputy", "Status", "Command", "CPU", "Mem", "Pid", "Priority", "Runtime", "Errors"])  # Set column names

        self.processTree.setFixedWidth(1000)
        self.leftVerticalLayout.addWidget(self.processTree)

        # Create the deputy table and add it to the left vertical layout
        self.deputyTable = QTableWidget(self.centralwidget)
        self.deputyTable.setObjectName("deputyTable")
        self.deputyTable.setColumnCount(8)  # Set the number of columns
        self.deputyTable.setHorizontalHeaderLabels(["Deputy", "IP", "Num Proc", "CPU", "Mem", "Net Send", "Net Recv", "Last Update"])  # Set column names
        self.deputyTable.verticalHeader().setVisible(False)  # Hide the vertical header
        self.deputyTable.resizeColumnsToContents()
        self.leftVerticalLayout.addWidget(self.deputyTable)

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
                    self.lcm_handler.create_process(process['deputy'], process['group'], process['name'], process['auto_restart'], process['cmd'], process["realtime"])
                    
                # Set the LCM channels from the file 
                # check if the file has the LCMChannels key
                if 'LCMChannels' in data:
                    deputy_info_channel = data['LCMChannels']['deputy_info_channel']
                    deputy_procs_channel = data['LCMChannels']['deputy_procs_channel']
                    proc_output_channel = data['LCMChannels']['proc_output_channel']
                    self.setLCMChannels(deputy_info_channel, deputy_procs_channel, proc_output_channel)
                
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
                    'deputy': process['deputy'],
                    'cmd': process['cmd'],
                    'group': process['group'],
                    'auto_restart': process['auto_restart'],
                    'realtime': process['realtime']
                }
                data['Processes'].append(process_info)
            
            data['LCMChannels'] = {}
            data['LCMChannels']['deputy_info_channel'] = self.deputy_info_channel
            data['LCMChannels']['deputy_procs_channel'] = self.deputy_procs_channel
            data['LCMChannels']['proc_output_channel'] = self.proc_output_channel

            # Save data to YAML file
            with open(fileName, 'w') as file:
                yaml.dump(data, file,Dumper=BlankLineDumper)
                
                
    def showProperties(self):
        dialog = PropertiesDialog(self.refresh_rate, self.udpm, self.deputy_info_channel, self.deputy_procs_channel, self.proc_output_channel)
        if dialog.exec_() == QDialog.Accepted:
            refresh_rate, udpm, deputy_info_channel, deputy_proc_channel, proc_output_channel = dialog.getValues()
            self.setProperties(refresh_rate, udpm)
            self.setLCMChannels(deputy_info_channel, deputy_proc_channel, proc_output_channel)
    
            
    def setProperties(self, refresh_rate, udpm):
         # stop the timer and start it with the new refresh rate
        self.refresh_rate = refresh_rate
        self.udpm = udpm
        self.timer.stop()
        self.timer.start(int(self.refresh_rate * 1000))
            
        # change the udpm in the lcm handler
        self.lcm_handler.change_udpm(self.udpm)
    
    def setLCMChannels(self, deputy_info_channel, deputy_proc_channel, proc_output_channel):
        self.deputy_info_channel = deputy_info_channel
        self.deputy_procs_channel = deputy_proc_channel
        self.proc_output_channel = proc_output_channel
        self.lcm_handler.change_channels(self.deputy_info_channel, self.deputy_procs_channel, self.proc_output_channel)
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
