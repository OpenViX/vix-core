from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.MenuList import MenuList
from Components.PluginComponent import plugins
from Components.Console import Console
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Wizard import WizardSummary
from Screens.WizardLanguage import WizardLanguage
from Screens.Wizard import wizardManager
from Screens.Rc import Rc
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS, SCOPE_SKIN_IMAGE
from Components.Pixmap import Pixmap, MovingPixmap, MultiPixmap
from os import popen, path, makedirs, listdir, access, stat, rename, remove, W_OK, R_OK
from enigma import eEnv

from Components.config import config, getConfigListEntry, ConfigSubsection, ConfigText, ConfigLocations, ConfigBoolean
from Components.Harddisk import harddiskmanager
config.misc.firstrun = ConfigBoolean(default = True)

backupfile = config.misc.boxtype.value + '-' + "enigma2settingsbackup.tar.gz"

def checkConfigBackup():
	parts = [ (r.description, r.mountpoint) for r in harddiskmanager.getMountedPartitions(onlyhotplug = False)]
	for x in parts:
		if x[1] == '/':
			parts.remove(x)
	if len(parts):
		for x in parts:
			if x[1].endswith('/'):
				fullbackupfile =  x[1] + 'backup/' + backupfile
				if fileExists(fullbackupfile):
					config.backupmanager.backuplocation.value = str(x[1])
					config.backupmanager.backuplocation.save()
					config.backupmanager.save()
					return x
			else:
				fullbackupfile =  x[1] + '/backup/' + backupfile
				if fileExists(fullbackupfile):
					config.backupmanager.backuplocation.value = str(x[1])
					config.backupmanager.backuplocation.save()
					config.backupmanager.save()
					return x
		return None		

def checkBackupFile():
	backuplocation = config.backupmanager.backuplocation.value
	if backuplocation.endswith('/'):
		fullbackupfile =  backuplocation + 'backup/' + backupfile
		if fileExists(fullbackupfile):
			return True
		else:
			return False
	else:
		fullbackupfile =  backuplocation + '/backup/' + backupfile
		if fileExists(fullbackupfile):
			return True
		else:
			return False

if checkConfigBackup() is None:
	backupAvailable = 0
else:
	backupAvailable = 1

class RestoreWizard(WizardLanguage, Rc):
	def __init__(self, session):
		self.xmlfile = resolveFilename(SCOPE_PLUGINS, "SystemPlugins/ViX/restorewizard.xml")
		WizardLanguage.__init__(self, session, showSteps = True, showStepSlider = True)
		Rc.__init__(self)
		self.skinName = "ImageWizard"
		self.skin = "ImageWizard.skin"
		self.session = session
		self["wizard"] = Pixmap()
		self.selectedDevice = None
		
	def markDone(self):
		pass

	def listDevices(self):
		list = [ (r.description, r.mountpoint) for r in harddiskmanager.getMountedPartitions(onlyhotplug = False)]
		for x in list:
			result = access(x[1], W_OK) and access(x[1], R_OK)
			if result is False or x[1] == '/':
				list.remove(x)
		for x in list:
			if x[1].startswith('/autofs/'):
				list.remove(x)	
		return list

	def deviceSelectionMade(self, index):
		self.deviceSelect(index)
		
	def deviceSelectionMoved(self):
		self.deviceSelect(self.selection)
		
	def deviceSelect(self, device):
		self.selectedDevice = device
		config.backupmanager.backuplocation.value = self.selectedDevice
		config.backupmanager.backuplocation.save()
		config.backupmanager.save()

def getBackupPath():
	backuppath = config.backupmanager.backuplocation.value
	if backuppath.endswith('/'):
		return backuppath + 'backup'
	else:
		return backuppath + '/backup'

def getBackupFilename():
	backupfile = config.misc.boxtype.value + '-' + "enigma2settingsbackup.tar.gz"
	return str(backupfile)
		

class RestoreSetting(Screen, ConfigListScreen):
	skin = """
		<screen position="135,144" size="350,310" title="Restore is running..." >
		<widget name="config" position="10,10" size="330,250" transparent="1" scrollbarMode="showOnDemand" />
		</screen>"""
		
	def __init__(self, session, runRestore = False):
		Screen.__init__(self, session)
		self.session = session
		self.runRestore = runRestore
		self["actions"] = ActionMap(["WizardActions", "DirectionActions"],
		{
			"ok": self.close,
			"back": self.close,
			"cancel": self.close,
		}, -1)
		self.finished_cb = None
		self.backuppath = getBackupPath()
		self.backupfile = getBackupFilename()
		self.fullbackupfilename = self.backuppath + "/" + self.backupfile
		self.list = []
		ConfigListScreen.__init__(self, self.list)
		self.onLayoutFinish.append(self.layoutFinished)
		if self.runRestore:
			self.onShown.append(self.doRestore)

	def layoutFinished(self):
		self.setWindowTitle()

	def setWindowTitle(self):
		self.setTitle(_("Restore is running..."))

	def doRestore(self):
		self.RestoreConsole = Console()
		if path.exists("/proc/stb/vmpeg/0/dst_width"):
			self.commands = ["tar -xzvf " + self.fullbackupfilename + " -C /", "echo 0 > /proc/stb/vmpeg/0/dst_height", "echo 0 > /proc/stb/vmpeg/0/dst_left", "echo 0 > /proc/stb/vmpeg/0/dst_top", "echo 0 > /proc/stb/vmpeg/0/dst_width"]
		else:
			self.commands = ["tar -xzvf " + self.fullbackupfilename + " -C /"]
		self.RestoreConsole.eBatch(self.commands, self.doRestorePlugins1, debug=True)

	def doRestorePlugins1(self, extra_args):
		self.RestoreConsole = Console()
		self.RestoreConsole.ePopen('opkg list-installed', self.doRestorePlugins2)

	def doRestorePlugins2(self, result, retval, extra_args):
		if retval == 0:
			pluginlist = file('/tmp/ExtraInstalledPlugins').readlines()
			plugins = []
			for line in result.split('\n'):
				if line:
					parts = line.strip().split()
					plugins.append(parts[0])
			output = open('/tmp/trimedExtraInstalledPlugins','a')
			for line in pluginlist:
				if line:
					parts = line.strip().split()
					if parts[0] not in plugins:
						output.write(parts[0] + '\n')
			output.close()
			self.doRestorePluginsQuestion()

	def doRestorePluginsQuestion(self, extra_args = None):
		plugintmp = file('/tmp/trimedExtraInstalledPlugins').read()
		pluginslist = plugintmp.replace('\n',' ')
		if pluginslist:
			message = _("Restore wizard has detected that you had extra plugins installed at the time of you backup, Do you want to reinstall these plugins ?")
			ybox = self.session.openWithCallback(self.doRestorePlugins3, MessageBox, message, MessageBox.TYPE_YESNO, wizard = True)
			ybox.setTitle(_("Re-install Plugins"))
		else:
			self.RestoreConsole = Console()
			self.RestoreConsole.ePopen("killall -9 enigma2")

	def doRestorePlugins3(self, answer):
		if answer is True:
			plugintmp = file('/tmp/trimedExtraInstalledPlugins').read()
			pluginslist = plugintmp.replace('\n',' ')
			self.commands = ["opkg update", "opkg install " + pluginslist, 'rm -f /tmp/ExtraInstalledPlugins', 'rm -f /tmp/trimedExtraInstalledPlugins']
			self.RestoreConsole.eBatch(self.commands,self.doRestorePlugins4, debug=True)
		else:
			self.RestoreConsole = Console()
			self.RestoreConsole.ePopen("killall -9 enigma2")

	def doRestorePlugins4(self, result):
		self.RestoreConsole = Console()
		self.RestoreConsole.ePopen("killall -9 enigma2")

	def backupFinishedCB(self,retval = None):
		self.close(True)

	def backupErrorCB(self,retval = None):
		self.close(False)

	def runAsync(self, finished_cb):
		self.finished_cb = finished_cb
		self.doRestore()

if config.misc.firstrun.value:
	wizardManager.registerWizard(RestoreWizard, backupAvailable, priority = 8)
