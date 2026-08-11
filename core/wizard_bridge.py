from PyQt5.QtCore import QObject, pyqtSignal
class WizardBridge(QObject):
    requestWizard = pyqtSignal(object)
    wizardDone = pyqtSignal()
    setActiveVillage = pyqtSignal(int)
bridge = WizardBridge()