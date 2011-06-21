#######################################################################
#
#    Vu HD plus skin setup for Enigma-2
#    Vesion 2.0
#    Coded by AndyBlac (c)2011
#    Support: andyblac@vuplus-support.co.uk
#
#    Some the code code is borrowed from Vali's Second InfoBar for Enigma-2
#
#    This program is free software; you can redistribute it and/or
#    modify it under the terms of the GNU General Public License
#    as published by the Free Software Foundation; either version 2
#    of the License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#######################################################################
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.config import config, ConfigSelection, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Language import language
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Tools.Directories import pathExists, resolveFilename, SCOPE_LANGUAGE, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from enigma import eTimer, getDesktop
from os import environ
import gettext

from CronManager import VIXCronManager
from MountManager import VIXDevicesPanel
from ImageManager import VIXImageManager, AutoImageManagerTimer, ImageManagerautostart
from IPKInstaller import VIXIPKInstaller
from ScriptRunner import VIXScriptRunner
from SwapManager import VIXSwap, SwapAutostart
from SoftcamManager import SoftcamAutoPoller, VIXSoftcamManager, SoftcamAutostart
from PowerManager import VIXPowerManager, AutoPowerManagerTimer, PowerManagerautostart, PowerManagerNextWakeup

_session = None

def Plugins(**kwargs):
	plist = [PluginDescriptor(name=_("VIXMenu"), where=PluginDescriptor.WHERE_MENU, fnc=startVIXMenu)]
	plist.append(PluginDescriptor(name="VIX",  where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=showVIXMenu))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SoftcamSetup))
	plist.append(PluginDescriptor(name=_("Softcam Manager"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=SoftcamMenu))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SwapAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SoftcamAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = PowerManagerautostart, wakeupfnc = PowerManagerNextWakeup))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = ImageManagerautostart))
	return plist

def startVIXMenu(menuid):
	if menuid == "setup":
		return [(_("VIX"), showVIXMenu, "vix_menu", 1010)]
	return [ ]

def showVIXMenu(session, **kwargs):
	session.open(VIXMenu)

def SoftcamSetup(menuid):
	if menuid == "cam":
		return [(_("Softcam Manager"), SoftcamMenu, "softcamsetup", 1005)]
	return []

def SoftcamMenu(session, **kwargs):
	session.open(VIXSoftcamManager)

#######################################################################

lang = language.getLanguage()
environ["LANGUAGE"] = lang[:2]
print "[VIXMainMenu] set language to ", lang[:2]
gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
gettext.textdomain("enigma2")
gettext.bindtextdomain("VIX", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "SystemPlugins/ViX/locale"))

def _(txt):
	t = gettext.dgettext("VIXMainMenu", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t

############################################################
# VIX Main Menu
############################################################
class VIXMenu(Screen):
	skin = """
		<screen name="VIXMenu" position="center,center" size="390,360" title="VIX">
		<widget position="100,30" render="Listbox" scrollbarMode="showOnDemand" size="310,300" source="list" transparent="1" zPosition="1">
			<convert type="StringList"/>
		</widget>
		</screen>"""

	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, "VIX")
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.KeyOk, 'back': self.close})
		self.list = []
		self['list'] = List(self.list)
		self.onChangedEntry = []
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self.updateList()

	def createSummary(self):
		return VIXMenuSummary
		
	def selectionChanged(self):
		item = self["list"].getCurrent()
		if item:
			name = item[0]
		else:
			name = "-"
		for cb in self.onChangedEntry:
			cb(name)

	def KeyOk(self):
		self.sel = self['list'].getCurrent()
		self.sel = self.sel[1]

		if self.sel == 0:
			self.session.open(VIXCronManager)
		elif self.sel == 1:
			self.session.open(VIXImageManager)
		elif self.sel == 2:
			self.session.open(VIXIPKInstaller)
		elif self.sel == 3:
			self.session.open(VIXDevicesPanel)
		elif self.sel == 4:
			self.session.open(VIXPowerManager)
		elif self.sel == 5:
			self.session.open(VIXScriptRunner)
		elif self.sel == 6:
			self.session.open(VIXSwap)

	def updateList(self):
		self.list = []
		name = _("Cron Manager")
		idx = 0
		res = (name, idx)
		self.list.append(res)
		name = _("Image Manager")
		idx = 1
		res = (name, idx)
		self.list.append(res)
		name = _("IPK Installer")
		idx = 2
		res = (name, idx)
		self.list.append(res)
		name = _("Mount Manager")
		idx = 3
		res = (name, idx)
		self.list.append(res)
		name = _("Power Manager")
		idx = 4
		res = (name, idx)
		self.list.append(res)
		name = _("Script Runner")
		idx = 5
		res = (name, idx)
		self.list.append(res)
		name = _("Swap Manager")
		idx = 6
		res = (name, idx)
		self.list.append(res)
		self['list'].list = self.list

class VIXMenuSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["entry"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name):
		self["entry"].text = name
