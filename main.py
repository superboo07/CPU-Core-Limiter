import sys
import psutil
import os
import keyboard
from PyQt5 import QtWidgets, QtGui
import xml.etree.ElementTree

class ProcessSelectorDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Select a running application')
        self.setGeometry(100, 100, 300, 400)

        layout = QtWidgets.QVBoxLayout()

        self.processListWidget = QtWidgets.QListWidget()
        self.updateProcessList()
        layout.addWidget(self.processListWidget)

        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        self.setLayout(layout)

    def updateProcessList(self):
        self.processListWidget.clear()
        processes = sorted(psutil.process_iter(['pid', 'name']), key=lambda p: p.info['name'].lower())
        for proc in processes:
            self.processListWidget.addItem(f"{proc.info['name']} (PID: {proc.info['pid']})")

    def getSelectedProcess(self):
        selected_item = self.processListWidget.currentItem()
        if selected_item:
            try:
                return int(selected_item.text().split('PID: ')[1].strip(')'))
            except (IndexError, ValueError):
                return None
        return None

def check_root_access():
    if os.name == 'nt':
        return  # Skip root check on Windows
    if os.geteuid() != 0:
        password, ok = QtWidgets.QInputDialog.getText(None, 'Root Password Required', 'Enter root password:', QtWidgets.QLineEdit.Password)
        if ok and password:
            command = f'echo {password} | sudo -S -p "" true'
            result = os.system(command)
            if result == 0:
                print("Root access granted")
                restart_with_root()
            else:
                print("Failed to gain root access")
                sys.exit(1)
        else:
            print("Root access required")
            sys.exit(1)

def restart_with_root():
    script_path = os.path.abspath(__file__)
    os.execvpe('sudo', ['sudo', 'python3', script_path], os.environ)

class CPULimiterUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.keyBindings = {}
        self.selected_executable = None
        self.loadKeyBindings()

    def initUI(self):
        self.setWindowTitle('CPU Core Limiter')
        self.setGeometry(100, 100, 400, 200)

        centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(centralWidget)

        layout = QtWidgets.QVBoxLayout()

        self.processLabel = QtWidgets.QLabel('Select a running application:')
        layout.addWidget(self.processLabel)

        self.coreUsageLabel = QtWidgets.QLabel('No application selected')
        layout.addWidget(self.coreUsageLabel)

        self.selectProcessButton = QtWidgets.QPushButton('Select Application')
        self.selectProcessButton.clicked.connect(self.openProcessSelector)
        layout.addWidget(self.selectProcessButton)

        self.processLabel.hide()

        self.coreLabel = QtWidgets.QLabel('Select number of CPU cores:')
        layout.addWidget(self.coreLabel)

        self.coreComboBox = QtWidgets.QComboBox()
        self.coreComboBox.addItems([str(i) for i in range(1, os.cpu_count() + 1)])
        layout.addWidget(self.coreComboBox)

        self.keyBindingsListWidget = QtWidgets.QListWidget()
        layout.addWidget(self.keyBindingsListWidget)

        buttonLayout = QtWidgets.QHBoxLayout()
        self.addKeyBindingButton = QtWidgets.QPushButton('Add Key Binding')
        self.addKeyBindingButton.clicked.connect(self.openKeyBinder)
        buttonLayout.addWidget(self.addKeyBindingButton)

        self.removeKeyBindingButton = QtWidgets.QPushButton('Remove Selected Key Binding')
        self.removeKeyBindingButton.clicked.connect(self.removeSelectedKeyBinding)
        buttonLayout.addWidget(self.removeKeyBindingButton)

        layout.addLayout(buttonLayout)

        self.limitButton = QtWidgets.QPushButton('Limit CPU Cores')
        self.limitButton.clicked.connect(self.limitCPUCores)
        layout.addWidget(self.limitButton)

        centralWidget.setLayout(layout)

    def openKeyBinder(self):
        dialog = KeyBinderDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            key, num_cores = dialog.getBinding()
            if key and num_cores and self.selected_executable:
                try:
                    formatted_key = key.lower().replace(' ', '+')
                    keyboard.add_hotkey(formatted_key, self.applyCPULimit, args=[num_cores])
                    if self.selected_executable not in self.keyBindings:
                        self.keyBindings[self.selected_executable] = []
                    self.keyBindings[self.selected_executable].append((formatted_key, num_cores))
                    print(f"Bound key {formatted_key} to {num_cores} CPU cores for {self.selected_executable}")
                    self.updateKeyBindingsList()
                    self.saveKeyBindings()
                except ValueError as e:
                    print(f"Error binding key: {e}")

    def removeSelectedKeyBinding(self):
        selected_item = self.keyBindingsListWidget.currentItem()
        if selected_item and self.selected_executable:
            key_binding_text = selected_item.text()
            key = key_binding_text.split(' -> ')[0].split(': ')[1]
            self.keyBindings[self.selected_executable] = [kb for kb in self.keyBindings[self.selected_executable] if kb[0] != key]
            keyboard.remove_hotkey(key)
            self.updateKeyBindingsList()
            self.saveKeyBindings()
            print(f"Removed key binding {key} for {self.selected_executable}")

    def updateKeyBindingsList(self):
        self.keyBindingsListWidget.clear()
        if self.selected_executable and self.selected_executable in self.keyBindings:
            for key, num_cores in self.keyBindings[self.selected_executable]:
                self.keyBindingsListWidget.addItem(f"Key: {key} -> {num_cores} CPU cores")

    def saveKeyBindings(self):
        root = xml.etree.ElementTree.Element("KeyBindings")
        for exe, bindings in self.keyBindings.items():
            exe_element = xml.etree.ElementTree.SubElement(root, "Executable", path=exe)
            for key, num_cores in bindings:
                binding = xml.etree.ElementTree.SubElement(exe_element, "Binding")
                xml.etree.ElementTree.SubElement(binding, "Key").text = key
                xml.etree.ElementTree.SubElement(binding, "NumCores").text = str(num_cores)
        tree = xml.etree.ElementTree.ElementTree(root)
        tree.write("keybindings.xml")

    def loadKeyBindings(self):
        if os.path.exists("keybindings.xml"):
            tree = xml.etree.ElementTree.parse("keybindings.xml")
            root = tree.getroot()
            for exe_element in root.findall("Executable"):
                exe = exe_element.get("path")
                self.keyBindings[exe] = []
                for binding in exe_element.findall("Binding"):
                    key = binding.find("Key").text
                    num_cores = int(binding.find("NumCores").text)
                    keyboard.add_hotkey(key, self.applyCPULimit, args=[num_cores])
                    self.keyBindings[exe].append((key, num_cores))
            self.updateKeyBindingsList()

    def openProcessSelector(self):
        dialog = ProcessSelectorDialog()
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            selected_pid = dialog.getSelectedProcess()
            if selected_pid:
                self.selected_pid = selected_pid
                self.selected_executable = psutil.Process(selected_pid).exe()
                self.processLabel.setText(f'Selected PID: {selected_pid} ({self.selected_executable})')
                self.processLabel.show()
                self.updateKeyBindingsList()
                self.updateCoreUsageLabel()

    def limitCPUCores(self):
        if hasattr(self, 'selected_pid'):
            pid = self.selected_pid
            num_cores = int(self.coreComboBox.currentText())
            p = psutil.Process(pid)
            p.cpu_affinity(list(range(num_cores)))
            print(f"Limited process {pid} to {num_cores} CPU cores")
            self.updateCoreUsageLabel()
        else:
            print("No process selected")

    def applyCPULimit(self, num_cores):
        if hasattr(self, 'selected_pid'):
            pid = self.selected_pid
            p = psutil.Process(pid)
            p.cpu_affinity(list(range(num_cores)))
            print(f"Limited process {pid} to {num_cores} CPU cores")
            self.updateCoreUsageLabel()

    def updateCoreUsageLabel(self):
        if hasattr(self, 'selected_pid'):
            pid = self.selected_pid
            p = psutil.Process(pid)
            num_cores = len(p.cpu_affinity())
            self.coreUsageLabel.setText(f"Current CPU core usage: {num_cores} cores")
        else:
            self.coreUsageLabel.setText("No application selected")

    def keyPressEvent(self, event):
        key = QtGui.QKeySequence(event.key()).toString()
        for binding_key, num_cores in self.keyBindings.get(self.selected_executable, []):
            if key == binding_key:
                print(f"{key} activated")
                if hasattr(self, 'selected_pid'):
                    pid = self.selected_pid
                    p = psutil.Process(pid)
                    p.cpu_affinity(list(range(num_cores)))
                break

class KeyBinderDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Bind Keys to CPU Core Counts')
        self.setGeometry(100, 100, 300, 200)

        layout = QtWidgets.QVBoxLayout()

        self.keyLabel = QtWidgets.QLabel('Press a key:')
        layout.addWidget(self.keyLabel)

        self.keyInput = QtWidgets.QLineEdit()
        self.keyInput.setReadOnly(True)
        layout.addWidget(self.keyInput)

        self.coreLabel = QtWidgets.QLabel('Select number of CPU cores:')
        layout.addWidget(self.coreLabel)

        self.coreComboBox = QtWidgets.QComboBox()
        self.coreComboBox.addItems([str(i) for i in range(1, os.cpu_count() + 1)])
        layout.addWidget(self.coreComboBox)

        self.bindButton = QtWidgets.QPushButton('Bind Key')
        self.bindButton.clicked.connect(self.accept)
        layout.addWidget(self.bindButton)

        self.setLayout(layout)

    def keyPressEvent(self, event):
        key = event.key()
        self.keyInput.setText(QtGui.QKeySequence(key).toString())

    def getBinding(self):
        key = self.keyInput.text()
        num_cores = int(self.coreComboBox.currentText())
        return key, num_cores

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    check_root_access()
    ex = CPULimiterUI()
    ex.show()
    sys.exit(app.exec_())
