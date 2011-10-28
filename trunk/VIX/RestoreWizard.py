# for localized messages
from . import _
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Console import Console
from Screens.Console import Console as RestoreConsole
from Components.config import config, ConfigBoolean
from Components.Harddisk import harddiskmanager
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Wizard import WizardSummary
from Screens.WizardLanguage import WizardLanguage
from Screens.Wizard import wizardManager
from Screens.Rc import Rc
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Components.Pixmap import Pixmap
from os import path, mkdir, listdir, access, stat, rename, remove, W_OK, R_OK

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
			else:
				fullbackupfile =  x[1] + '/backup/' + backupfile
			if path.exists(fullbackupfile):
				config.backupmanager.backuplocation.value = str(x[1])
				config.backupmanager.backuplocation.save()
				config.backupmanager.save()
				return x
		return None		

def checkBackupFile():
	backuplocation = config.backupmanager.backuplocation.value
	if backuplocation.endswith('/'):
		fullbackupfile =  backuplocation + 'backup/' + backupfile
	else:
		fullbackupfile =  backuplocation + '/backup/' + backupfile
	if path.exists(fullbackupfile):
		return True
	else:
		if config.misc.boxtype.value == 'et9x00':
			backupfile = "et9000-enigma2settingsbackup.tar.gz"
		elif config.misc.boxtype.value == 'et5x00':
			backupfile = "et5000-enigma2settingsbackup.tar.gz"
		if backuplocation.endswith('/'):
			fullbackupfile =  backuplocation + 'backup/' + backupfile
		else:
			fullbackupfile =  backuplocation + '/backup/' + backupfile
		if path.exists(fullbackupfile):
			return True
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
		self.setTitle(_("Restore is running..."))
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
		if self.runRestore:
			self.onShown.append(self.doRestore)

	def doRestore(self):
		self.Console = Console()
		self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + " -C /", self.doRestorePlugins1)

	def doRestorePlugins1(self, result, retval, extra_args):
		self.Console.ePopen('opkg list-installed', self.doRestorePlugins2)

	def doRestorePlugins2(self, result, retval, extra_args):
		if retval == 0:
			if path.exists('/tmp/ExtraInstalledPlugins'):
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
							output.write(parts[0] + ' ')
				output.close()
				self.doRestorePluginsQuestion()

	def doRestorePluginsQuestion(self, extra_args = None):
		fstabfile = file('/etc/fstab').readlines()
		for mountfolder in fstabfile:
			parts = mountfolder.strip().split()
			if parts and str(parts[0]).startswith('/dev/'):
				if not path.exists(parts[1]):
					mkdir(parts[1], 0755)				
		pluginslist = file('/tmp/trimedExtraInstalledPlugins').read()
		if pluginslist:
			message = _("Restore wizard has detected that you had extra plugins installed at the time of you backup, Do you want to reinstall these plugins ?")
			ybox = self.session.openWithCallback(self.doRestorePlugins3, MessageBox, message, MessageBox.TYPE_YESNO, wizard = True)
			ybox.setTitle(_("Re-install Plugins"))
		else:
			self.Console.ePopen("init 3 && reboot")

	def doRestorePlugins3(self, answer):
		if answer is True:
			plugintmp = file('/tmp/trimedExtraInstalledPlugins').read()
			pluginslist = plugintmp.replace('\n',' ')
			mycmd1 = "echo '************************************************************************'"
			if config.misc.boxtype.value.startswith('vu'):
				mycmd2 = "echo 'Vu+ " + config.misc.boxtype.value +  _(" detected'")
			elif config.misc.boxtype.value.startswith('et'):
				mycmd2 = "echo 'Xtrend " + config.misc.boxtype.value +  _(" detected'")
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "echo ' '"
			mycmd5 = _("echo 'Attention:'")
			mycmd6 = "echo ' '"
			mycmd7 = _("echo 'Enigma2 will be restarted automatically after the restore progress.'")
			mycmd8 = "echo ' '"
			mycmd9 = _("echo 'Installing Plugins.'")
			mycmd10 = "opkg update"
			mycmd11 = "opkg install " + pluginslist
			mycmd12 = 'rm -f /tmp/trimedExtraInstalledPlugins'
			mycmd13 = "init 3 && reboot"
			self.session.open(RestoreConsole, title=_('Installing Plugins...'), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13],closeOnSuccess = True)
		else:
			self.Console.ePopen("init 3 && reboot")

	def backupFinishedCB(self,retval = None):
		self.close(True)

	def backupErrorCB(self,retval = None):
		self.close(False)

	def runAsync(self, finished_cb):
		self.finished_cb = finished_cb
		self.doRestore()

if config.misc.firstrun.value:
	wizardManager.registerWizard(RestoreWizard, backupAvailable, priority = 8)
