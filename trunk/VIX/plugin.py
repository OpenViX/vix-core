# for localized messages
from . import _

from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Components.config import config
from Components.MultiContent import MultiContentEntryText
from Components.PluginComponent import plugins
from Components.Language import language
from enigma import eTimer, quitMainloop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, gFont

from SoftwareManager import PluginManager, UpdatePlugin, PacketManager

from RestoreWizard import RestoreWizard
from BackupManager import VIXBackupManager, AutoBackupManagerTimer, BackupManagerautostart
from CronManager import VIXCronManager
from MountManager import VIXDevicesPanel
from ImageManager import VIXImageManager, AutoImageManagerTimer, ImageManagerautostart
from IPKInstaller import VIXIPKInstaller
from ScriptRunner import VIXScriptRunner
from SwapManager import VIXSwap, SwapAutostart
from SoftcamManager import SoftcamAutoPoller, VIXSoftcamManager, SoftcamAutostart
from PowerManager import VIXPowerManager, AutoPowerManagerTimer, PowerManagerautostart, PowerManagerNextWakeup

_session = None

#######################################################################

class VIXMenu(Screen):
	skin = """
		<screen name="VIXMenu" position="center,center" size="610,410" title="Software management" >
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
		self.menutext = _("Press MENU on your remote control for additional options.")
		self.text = ""
		if self.menu == 0:
			self.list.append(("backup-manager", _("Backup Manager"), _("\nManage your backups of your settings." ), None))
			self.list.append(("cron-manager", _("Cron Manager"), _("\nManage your cron jobs." ), None))
			self.list.append(("image-manager", _("Image Manager"), _("\nCreate and Restore complete images of the system." ), None))
			self.list.append(("ipkg-install", _("Install local extension"),  _("\nInstall IPK's from your tmp folder." ), None))
			self.list.append(("install-extensions", _("Manage Extensions"), _("\nManage extensions or plugins for your receiver" ), None))
			self.list.append(("mount-manager",_("Mount Manager"), _("\nManage you devices mountpoints." ), None))
			self.list.append(("ipkg-manager", _("Packet Manager"),  _("\nView, install and remove available or installed packages." ), None))
			self.list.append(("power-manager",_("Power Manager"), _("\nCreate schedules for Standby, Restart GUI, DeepStandby and Reboot."), None))
			self.list.append(("script-runner",_("Script Running"), _("\nRun your shell scripts." ), None))
			self.list.append(("software-update", _("Software Update"), _("\nOnline update of your Receiver software." ), None))
			self.list.append(("swap-manager",_("Swap Manager"), _("\nCreate and Manage your swapfiles." ), None))

			for p in plugins.getPlugins(PluginDescriptor.WHERE_SOFTWAREMANAGER):
				if p.__call__.has_key("SoftwareSupported"):
					callFnc = p.__call__["SoftwareSupported"](None)
					if callFnc is not None:
						if p.__call__.has_key("menuEntryName"):
							menuEntryName = p.__call__["menuEntryName"](None)
						else:
							menuEntryName = _("Extended Software")
						if p.__call__.has_key("menuEntryDescription"):
							menuEntryDescription = p.__call__["menuEntryDescription"](None)
						else:
							menuEntryDescription = _("Extended Software Plugin")
						self.list.append(('default-plugin', menuEntryName, menuEntryDescription, callFnc))

		self["menu"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["status"] = StaticText(self.menutext)

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions", "InfobarEPGActions", "MenuActions"],
		{
			"ok": self.go,
			"back": self.close,
			"red": self.close,
		}, -1)
		self.onLayoutFinish.append(self.layoutFinished)
		self.onShown.append(self.setWindowTitle)
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

	def cleanup(self):
		iSoftwareTools.cleanupSoftwareTools()

	def getUpdateInfos(self):
		self.text = ""
		if iSoftwareTools.NetworkConnectionAvailable == True:
			if iSoftwareTools.list_updating is False:
				if iSoftwareTools.available_updates is not 0:
					self.text = _("There are at least ") + str(iSoftwareTools.available_updates) + _(" updates available.")
				else:
					self.text = "" #_("There are no updates available.")
			else:
				if iSoftwareTools.available_updates is not 0:
					self.text = _("There are at least ") + str(iSoftwareTools.available_updates) + _(" updates available.")
				else:
					self.text = ""  #_("There are no updates available.")
				self.text += "\n" + _("A search for available updates is currently in progress.")
		else:
			self.text = _("No network connection available.")
		self["status"].setText(self.text)

	def go(self):
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if self.menu == 0:
				if (currentEntry == "install-extensions"):
					self.session.open(PluginManager, self.skin_path)
				elif (currentEntry == "software-update"):
					self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to update your Receiver?")+"\n"+_("\nAfter pressing OK, please wait!"))
				elif (currentEntry == "backup-manager"):
					self.session.open(VIXBackupManager)
				elif (currentEntry == "cron-manager"):
					self.session.open(VIXCronManager)
				elif (currentEntry == "image-manager"):
					self.session.open(VIXImageManager)
				elif (currentEntry == "ipkg-install"):
					self.session.open(VIXIPKInstaller)
				elif (currentEntry == "mount-manager"):
					self.session.open(VIXDevicesPanel)
				elif (currentEntry == "power-manager"):
					self.session.open(VIXPowerManager)
				elif (currentEntry == "script-runner"):
					self.session.open(VIXScriptRunner)
				elif (currentEntry == "swap-manager"):
					self.session.open(VIXSwap)
				elif (currentEntry == "default-plugin"):
					self.extended = current[3]
					self.extended(self.session, None)
				elif (currentEntry == "ipkg-manager"):
					self.session.open(PacketManager, self.skin_path)

	def runUpgrade(self, result):
		if result:
			self.session.open(UpdatePlugin, self.skin_path)

	def runUpgradeOffline(self, result):
		if result:
			self.session.open(UpdatePlugin, self.skin_path, 'offline')

def UpgradeMain(session, **kwargs):
	session.open(VIXMenu)

def startSetup(menuid):
	if menuid != "setup": 
		return [ ]
	return [(_("VIX"), UpgradeMain, "vix_menu", 1010)]

def Plugins(path, **kwargs):
	global plugin_path
	plugin_path = path
	plist = [PluginDescriptor(name=_("VIXMenu"), where=PluginDescriptor.WHERE_MENU, needsRestart = False, fnc=startSetup)]
	plist.append(PluginDescriptor(name=_("VIX"),  where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=UpgradeMain))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SoftcamSetup))
	plist.append(PluginDescriptor(name=_("Softcam Manager"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=SoftcamMenu))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SwapAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SoftcamAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = PowerManagerautostart, wakeupfnc = PowerManagerNextWakeup))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = ImageManagerautostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = BackupManagerautostart))
	return plist

def SoftcamSetup(menuid):
	if menuid == "cam":
		return [(_("Softcam Manager"), SoftcamMenu, "softcamsetup", 1005)]
	return []

def SoftcamMenu(session, **kwargs):
	session.open(VIXSoftcamManager)
