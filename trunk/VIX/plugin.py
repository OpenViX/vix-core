# for localized messages
from . import _

from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Components.MultiContent import MultiContentEntryText
from Components.config import config, ConfigBoolean
from Components.Harddisk import harddiskmanager
from enigma import RT_HALIGN_LEFT, RT_VALIGN_CENTER, gFont
from os import path, mkdir, listdir, access, stat, rename, remove, W_OK, R_OK

from BackupManager import BackupManagerautostart
from ImageManager import ImageManagerautostart
from SwapManager import SwapAutostart
from SoftcamManager import SoftcamAutostart
from PowerManager import PowerManagerautostart, PowerManagerNextWakeup

def checkConfigBackup():
	devices = [ (r.description, r.mountpoint) for r in harddiskmanager.getMountedPartitions(onlyhotplug = False)]
	list = []
	for x in devices:
		if x[1] == '/':
			devices.remove(x)
	if len(devices):
		for x in devices:
			print '[RestoreWizard] Seraching devices:',x
			if not x[1].endswith('/'):
				if path.exists(x[1] + '/backup'):
					images = listdir(x[1] + '/backup')
			else:
				if path.exists(x[1] + 'backup'):
					images = listdir(x[1] + 'backup')
			if len(images):
				for fil in images:
					if fil.endswith('.tar.gz') and fil.startswith(config.misc.boxtype.value):
						if not x[1].endswith('/'):
							list.append((x[1] + '/backup/' + fil,x[1] + '/backup/' + fil))
						else:
							list.append((x[1] + 'backup/' + fil,x[1] + 'backup/' + fil))
	if len(list):
		return True
	else:
		return None

if checkConfigBackup() is None:
	backupAvailable = 0
else:
	backupAvailable = 1

class VIXMenu(Screen):
	skin = """
		<screen name="VIXMenu" position="center,center" size="610,410" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<ePixmap pixmap="skin_default/border_menu_350.png" position="5,50" zPosition="1" size="350,300" transparent="1" alphatest="on" />
			<widget source="menu" render="Listbox" position="15,60" size="330,290" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (2, 2), size = (330, 24), flags = RT_HALIGN_LEFT, text = 1), # index 0 is the MenuText,
						],
					"fonts": [gFont("Regular", 22)],
					"itemHeight": 25
					}
				</convert>
			</widget>
			<widget source="menu" render="Listbox" position="360,50" size="240,300" scrollbarMode="showNever" selectionDisabled="1">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (2, 2), size = (240, 300), flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER|RT_WRAP, text = 2), # index 2 is the Description,
						],
					"fonts": [gFont("Regular", 22)],
					"itemHeight": 300
					}
				</convert>
			</widget>
			<widget source="status" render="Label" position="5,360" zPosition="10" size="600,50" halign="center" valign="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		</screen>"""
		
	def __init__(self, session, args = 0):
		Screen.__init__(self, session)
		self.skin_path = plugin_path
		self.menu = args
		self.list = []
		if self.menu == 0:
			self.list.append(("backup-manager", _("Backup Manager"), _("\nManage your backups of your settings." ), None))
			self.list.append(("cron-manager", _("Cron Manager"), _("\nManage your cron jobs." ), None))
			self.list.append(("image-manager", _("Image Manager"), _("\nCreate and Restore complete images of the system." ), None))
			self.list.append(("ipkg-install", _("Install local extension"),  _("\nInstall IPK's from your tmp folder." ), None))
			self.list.append(("install-extensions", _("Manage Extensions"), _("\nManage extensions or plugins for your receiver" ), None))
			self.list.append(("mount-manager",_("Mount Manager"), _("\nManage you devices mountpoints." ), None))
			self.list.append(("ipkg-manager", _("Packet Manager"),  _("\nView, install and remove available or installed packages." ), None))
			self.list.append(("power-manager",_("Power Manager"), _("\nCreate schedules for Standby, Restart GUI, DeepStandby and Reboot."), None))
			self.list.append(("script-runner",_("Script Runner"), _("\nRun your shell scripts." ), None))
			self.list.append(("software-update", _("Software Update"), _("\nOnline update of your Receiver software." ), None))
			self.list.append(("swap-manager",_("Swap Manager"), _("\nCreate and Manage your swapfiles." ), None))
		self["menu"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions", "InfobarEPGActions", "MenuActions"],
		{
			"ok": self.go,
			"back": self.close,
			"red": self.close,
		}, -1)
		self.onLayoutFinish.append(self.layoutFinished)
		self.onChangedEntry = []
		self["menu"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["menu"].getCurrent()
		if item:
			name = item[1]
			desc = item[2]
		else:
			name = "-"
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def layoutFinished(self):
		idx = 0
		self["menu"].index = idx

	def setWindowTitle(self):
		self.setTitle(_("ViX"))

	def go(self):
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if self.menu == 0:
				if (currentEntry == "backup-manager"):
					from BackupManager import VIXBackupManager
					self.session.open(VIXBackupManager)
				elif (currentEntry == "cron-manager"):
					from CronManager import VIXCronManager
					self.session.open(VIXCronManager)
				elif (currentEntry == "image-manager"):
					from ImageManager import VIXImageManager
					self.session.open(VIXImageManager)
				elif (currentEntry == "install-extensions"):
					from SoftwareManager import PluginManager
					self.session.open(PluginManager, self.skin_path)
				elif (currentEntry == "ipkg-install"):
					from IPKInstaller import VIXIPKInstaller
					self.session.open(VIXIPKInstaller)
				elif (currentEntry == "ipkg-manager"):
					from SoftwareManager import PacketManager
					self.session.open(PacketManager, self.skin_path)
				elif (currentEntry == "mount-manager"):
					from MountManager import VIXDevicesPanel
					self.session.open(VIXDevicesPanel)
				elif (currentEntry == "power-manager"):
					from PowerManager import VIXPowerManager
					self.session.open(VIXPowerManager)
				elif (currentEntry == "script-runner"):
					from ScriptRunner import VIXScriptRunner
					self.session.open(VIXScriptRunner)
				elif (currentEntry == "software-update"):
					from SoftwareManager import UpdatePlugin
					self.session.open(UpdatePlugin, self.skin_path)
				elif (currentEntry == "swap-manager"):
					from SwapManager import VIXSwap
					self.session.open(VIXSwap)

class VIXMenuSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["entry"] = StaticText("")
		self["desc"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name, desc):
		self["entry"].text = name
		self["desc"].text = desc

def UpgradeMain(session, **kwargs):
	session.open(VIXMenu)

def startSetup(menuid):
	if menuid != "setup": 
		return [ ]
	return [(_("ViX"), UpgradeMain, "vix_menu", 1010)]

config.misc.restorewizardrun = ConfigBoolean(default = False)
def RestoreWizard(*args, **kwargs):
	from RestoreWizard import RestoreWizard
	return RestoreWizard(*args, **kwargs)

def Plugins(path, **kwargs):
	global plugin_path
	plugin_path = path
	plist = [PluginDescriptor(name=_("VIXMenu"), where=PluginDescriptor.WHERE_MENU, needsRestart = False, fnc=startSetup)]
	plist.append(PluginDescriptor(name=_("ViX"),  where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=UpgradeMain))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SoftcamSetup))
	plist.append(PluginDescriptor(name=_("Softcam Manager"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=SoftcamMenu))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SwapAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SoftcamAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = PowerManagerautostart, wakeupfnc = PowerManagerNextWakeup))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = ImageManagerautostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = BackupManagerautostart))
	if config.misc.firstrun.value and not config.misc.restorewizardrun.value:
		plist.append(PluginDescriptor(name=_("Restore Wizard"), where = PluginDescriptor.WHERE_WIZARD, needsRestart = False, fnc=(8, RestoreWizard)))
	return plist

def SoftcamSetup(menuid):
	if menuid == "cam":
		return [(_("Softcam Manager"), SoftcamMenu, "softcamsetup", 1005)]
	return []

def SoftcamMenu(session, **kwargs):
	from SoftcamManager import VIXSoftcamManager
	session.open(VIXSoftcamManager)
