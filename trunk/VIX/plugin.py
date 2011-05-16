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
import Components.Task
from Components.ActionMap import ActionMap, NumberActionMap
from Components.Button import Button
from Components.config import config, ConfigSelection, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Harddisk import harddiskmanager
from Components.Label import Label
from Components.Language import language
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop, Standby
from Tools.Directories import fileExists, pathExists, resolveFilename, SCOPE_LANGUAGE, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from twisted.internet import reactor, threads, task
from time import localtime, time, strftime
from enigma import eTimer, getDesktop
from os import system, environ, remove, rename, path, chmod
from glob import glob
import gettext

# Partnerbox installed and icons in epglist enabled?
try:
	from Plugins.Extensions.Partnerbox.plugin import PartnerboxSetup
except ImportError:
	pass
try:
	from Plugins.SystemPlugins.CrossEPG.crossepg_menu import CrossEPG_Menu
except ImportError:
	pass
try:
	from Plugins.Extensions.EPGImport.plugin import EPGMainSetup, doneConfiguring
except ImportError:
	pass

from CronManager import VIXCronManager
from DeviceManager import VIXDevicesPanel
from ImageManager import VIXImageManager
from IPKInstaller import VIXIPKInstaller
from ScriptRunner import VIXScriptRunner
from SwapManager import VIXSwap, SwapAutostart
from SoftcamManager import SoftcamAutoPoller, VIXSoftcamManager, SoftcamAutostart
from PowerManager import VIXPowerManager, AutoPowerManagerTimer, PowerManagerautostart, PowerManagerNextWakeup
from CCcamInfo import CCcamInfoMain
from OScamInfo import OscamInfoMenu

_session = None

fb = getDesktop(0).size()
if fb.width() > 1024:
	sizeH = fb.width() - 100
	HDSKIN = True
else:
	# sizeH = fb.width() - 50
	sizeH = 700
	HDSKIN = False

def Plugins(**kwargs):
	plist = [PluginDescriptor(name=_("VIXMenu"), where=PluginDescriptor.WHERE_MENU, fnc=startVIXMenu)]
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=startVIXSettings))
	plist.append(PluginDescriptor(name="VIX",  where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=showVIXMenu))
	plist.append(PluginDescriptor(name="CCcam Info",  where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=CCcamInfo))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=CCcamInfoMenu))
	plist.append(PluginDescriptor(name="OScam Info",  where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=OScamInfo))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=OScamInfoMain))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SoftcamSetup))
	plist.append(PluginDescriptor(name=_("Softcam Manager"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=SoftcamMenu))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = AutoVersionCheck))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = autostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SwapAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_AUTOSTART, fnc = SoftcamAutostart))
	plist.append(PluginDescriptor(where = PluginDescriptor.WHERE_SESSIONSTART, fnc = PowerManagerautostart, wakeupfnc = PowerManagerNextWakeup))
	return plist

def startVIXMenu(menuid):
	if menuid == "setup":
		return [(_("VIX"), showVIXMenu, "vix_menu", 1010)]
	return [ ]

def startVIXSettings(menuid):
	if menuid == "system":
		return [(_("VIX"), showVIXSettings, "vix_settings", 1010)]
	return [ ]

def showVIXMenu(session, **kwargs):
	session.open(VIXMenu)

def showVIXSettings(session, **kwargs):
	session.open(VIXSetup)

def OScamInfoMain(menuid):
	if menuid == "cam":
		return [(_("OScam Info"), OScamInfo, "oscam_info", None)]
	return [ ]

def OScamInfo(session, **kwargs):
	global HDSKIN, sizeH
	session.open(OscamInfoMenu)

def CCcamInfoMenu(menuid):
	if menuid == "cam":
		return [(_("CCcam Info"), CCcamInfo, "cccam_info", None)]
	return [ ]

def CCcamInfo(session, **kwargs):
	session.open(CCcamInfoMain)

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

def autostart(reason, session = None):
	if reason == 0:
		if config.plugins.ViXSettings.enabledebug.value:
			inputfile = "/usr/bin/enigma2.sh"
			outputfile = inputfile+'.tmp'
			stext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2\n'
			rtext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2 &>/home/root/Enigma2-$(date +%d-%m-%Y_%H-%M-%S).log\n'
			input = open(inputfile)
			output = open(outputfile,'w')
			for s in input:
				output.write(s.replace(stext,rtext))
			output.close()
			input.close()
			remove(inputfile)
			rename(outputfile,inputfile)
			chmod('/usr/bin/enigma2.sh',0755)
			print '[DEBUG] Enabled'
		elif not config.plugins.ViXSettings.enabledebug.value:
			inputfile = "/usr/bin/enigma2.sh"
			outputfile = inputfile+'.tmp'
			stext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2 /usr/bin/enigma2 &>/home/root/Enigma2-$(date +%d-%m-%Y_%H-%M-%S).log\n'
			rtext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2\n'
			input = open(inputfile)
			output = open(outputfile,'w')
			for s in input:
				output.write(s.replace(stext,rtext))
			output.close()
			input.close()
			remove(inputfile)
			rename(outputfile,inputfile)
			print '[DEBUG] Disabled'
			chmod('/usr/bin/enigma2.sh',0755)


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
		self["title"] = Label(_("VIX"))
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
			if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/CrossEPG/plugin.pyo"):
				self.session.open(CrossEPG_Menu)
		elif self.sel == 2:
			self.session.open(VIXDevicesPanel)
		elif self.sel == 3:
			self.session.open(VIXImageManager)
		elif self.sel == 4:
			self.session.open(VIXIPKInstaller)
		elif self.sel == 5:
			self.session.open(VIXPowerManager)
		elif self.sel == 6:
			self.session.open(VIXScriptRunner)
		elif self.sel == 7:
			self.session.open(VIXSwap)
		elif self.sel == 8:
			self.session.openWithCallback(doneConfiguring, EPGMainSetup)

	def updateList(self):
		self.list = []
		name = _("Cron Manager")
		idx = 0
		res = (name, idx)
		self.list.append(res)
		if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/CrossEPG/plugin.pyo"):
			name = _("CrossEPG")
			idx = 1
			res = (name, idx)
			self.list.append(res)
		name = _("Devices Manager")
		idx = 2
		res = (name, idx)
		self.list.append(res)
		name = _("Image Manager")
		idx = 3
		res = (name, idx)
		self.list.append(res)
		name = _("IPK Installer")
		idx = 4
		res = (name, idx)
		self.list.append(res)
		name = _("Power Manager")
		idx = 5
		res = (name, idx)
		self.list.append(res)
		name = _("Script Runner")
		idx = 6
		res = (name, idx)
		self.list.append(res)
		name = _("Swap Manager")
		idx = 7
		res = (name, idx)
		self.list.append(res)
		name = _("XMLTV-Importer")
		idx = 8
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

class VIXSetup(ConfigListScreen, Screen):
	skin = """
		<screen name="VIXSetup" position="center,center" size="500,330" title="VIX Setup">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="config" position="10,45" size="480,320" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.skin = VIXSetup.skin
		self.skinName = "VIXSetup"
		self["title"] = Label(_("VIX Setup"))
		self.skinfile = "/usr/share/enigma2/ViX_HD/skin.xml"
		self.mountpoint = []
		self.mountdescription = []
		self.restartneeded = False
		self.olddebug = config.plugins.ViXSettings.enabledebug.value
		self.oldoverscan = config.plugins.ViXSettings.overscanamount.value
		self.epgcache_filename = config.misc.epgcache_filename.value

		epgdata = []
		for p in harddiskmanager.getMountedPartitions():
			d = path.normpath(p.mountpoint)
			if pathExists(p.mountpoint):
				if p.mountpoint == '/':
					epgdata.append(('/hdd/epg.dat', p.description))
				else:
					epgdata.append((d + '/epg.dat', p.mountpoint))
		if len(epgdata):
			print 'epgdata ' + str(epgdata)
			config.misc.epgcache_filename = ConfigSelection(default = "/hdd/epg.dat", choices = epgdata)

		self.onChangedEntry = [ ]

		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self.createSetup()
		
		self["actions"] = NumberActionMap(["SetupActions"],
		{
		  "cancel": self.keyCancel,
		  "save": self.keySaveNew
		}, -2)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))

	def createSetup(self):
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Menu Overscan amount"), config.plugins.ViXSettings.overscanamount))
		self.list.append(getConfigListEntry(_("Choose EPG location"), config.misc.epgcache_filename))
		self.list.append(getConfigListEntry(_("Use TV button to"), config.plugins.ViXSettings.TVButtonAction))
		self.list.append(getConfigListEntry(_("Use ViX Coloured Butons"), config.plugins.ViXSettings.ColouredButtons))
		self.list.append(getConfigListEntry(_("Subservice (Green)"), config.plugins.ViXSettings.Subservice))
		self.list.append(getConfigListEntry(_("EPG buton mode"), config.plugins.ViXEPG.mode))
		self.list.append(getConfigListEntry(_("QuickEPG Usage"), config.plugins.QuickEPG.mode))
		self.list.append(getConfigListEntry(_('Show event info on 2nd "OK"'), config.plugins.ViXSettings.InfoBarMode))
		self.list.append(getConfigListEntry(_("Enable Debug logs"), config.plugins.ViXSettings.enabledebug))
		if config.plugins.ViXSettings.enabledebug.value:
			self.list.append(getConfigListEntry(_("Clean Debug logs"), config.plugins.ViXSettings.cleandebug))
		self["config"].list = self.list
		self["config"].setList(self.list)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.createSetup()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.createSetup()

	# for summary:
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def keySaveNew(self):
		print 'EPG location ', config.misc.epgcache_filename.value
		for x in self["config"].list:
			x[1].save()

		if self.olddebug != config.plugins.ViXSettings.enabledebug.value or self.oldoverscan != config.plugins.ViXSettings.overscanamount.value or self.epgcache_filename != config.misc.epgcache_filename.value:
			self.restartneeded = True

		if config.plugins.ViXSettings.enabledebug.value:
			inputfile = "/usr/bin/enigma2.sh"
			outputfile = inputfile+'.tmp'
			stext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2\n'
			rtext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2 &>/home/root/Enigma2-$(date +%d-%m-%Y_%H-%M-%S).log\n'
			input = open(inputfile)
			output = open(outputfile,'w')
			for s in input:
				output.write(s.replace(stext,rtext))
			output.close()
			input.close()
			remove(inputfile)
			rename(outputfile,inputfile)
			chmod('/usr/bin/enigma2.sh',0755)
			print '[DEBUG] Enabled'
		elif not config.plugins.ViXSettings.enabledebug.value:
			inputfile = "/usr/bin/enigma2.sh"
			outputfile = inputfile+'.tmp'
			stext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2 /usr/bin/enigma2 &>/home/root/Enigma2-$(date +%d-%m-%Y_%H-%M-%S).log\n'
			rtext = 'LD_PRELOAD=/usr/lib/libopen.so.0.0.0 /usr/bin/enigma2\n'
			input = open(inputfile)
			output = open(outputfile,'w')
			for s in input:
				output.write(s.replace(stext,rtext))
			output.close()
			input.close()
			remove(inputfile)
			rename(outputfile,inputfile)
			print '[DEBUG] Disabled'
			chmod('/usr/bin/enigma2.sh',0755)

		if not config.plugins.ViXSettings.enabledebug.value or config.plugins.ViXSettings.cleandebug.value:
			for filename in glob('/home/root/*.log') :
			    remove(filename)
			print '[DEBUG] Logs Cleaned'

		if config.plugins.ViXSettings.overscanamount.value <= "0":
			inputfile = "/usr/share/enigma2/ViX_HD/skin.xml"
			outputfile = inputfile+'.tmp'
			skinposinputfile = '/usr/share/enigma2/ViX_HD/skinpos.loc'
			skinposoutputfile = '/usr/share/enigma2/ViX_HD/skinpos.tmp'
			if pathExists(skinposinputfile):
				skinposinput = open(skinposinputfile,'r')
				stext = skinposinput.readline()
			else:
				stext = 'position="32,0" size="541,720"'
			rtext = 'position="' + str(config.plugins.ViXSettings.overscanamount.value) + ',0" size="541,720"'
			print '[SEARCH] ' + stext
			print '[REPLACE] ' + rtext

			input = open(inputfile)
			output = open(outputfile,'w')
			for s in input:
				output.write(s.replace(stext,rtext))
			output.close()
			input.close()
			remove(inputfile)
			rename(outputfile,inputfile)
			skinposoutput = open(skinposoutputfile,'w')
			skinposoutput.write(rtext)
			skinposoutput.close()
			if pathExists(skinposinputfile):
				skinposinput.close()
				remove(skinposinputfile)
			rename(skinposoutputfile,skinposinputfile)

		if self.restartneeded:
			message = _("GUI needs a restart to apply the changes !!!\nDo you want to restart GUI now ?")
			ybox = self.session.openWithCallback(self.restBox, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Restart Enigma2."))
		else:
			self.close()
					
	def restBox(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 3)
		else:
			self.close()

	def keyCancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close()

def AutoVersionCheck(reason, session=None, **kwargs):
	"called with reason=1 to during shutdown, with reason=0 at startup?"
	global versioncheckpoller
	if reason == 0:
		print "[OnlineVersionCheck] AutoStart Enabled"
		versioncheckpoller = VersionCheckPoller()
		versioncheckpoller.start()
	elif reason == 1:
		# Stop Poller
		if versioncheckpoller is not None:
			versioncheckpoller.stop()
			versioncheckpoller = None


class VersionCheckPoller:
	"""Automatically Poll SoftCam"""
	def __init__(self):
		# Init Timer
		self.timer = eTimer()

	def start(self, initial = True):
		if initial:
			delay = 0
		else:
			delay = 86400 #once a day

		if self.version_check not in self.timer.callback:
			self.timer.callback.append(self.version_check)
		self.timer.startLongTimer(delay)

	def stop(self):
		if self.version_check in self.timer.callback:
			self.timer.callback.remove(self.version_check)
		self.timer.stop()

	def version_check(self):
		now = int(time())
		print "[VersionCheck] Poll occured at", strftime("%c", localtime(now))
		name = _("OnlineCheck")
		job = Components.Task.Job(name)
		task = CheckTask(job, name)
		Components.Task.job_manager.AddJob(job)
		self.timer.startLongTimer(86400) #once a day

class FailedPostcondition(Components.Task.Condition):
	def __init__(self, exception):
		self.exception = exception
	def getErrorMessage(self, task):
		return str(self.exception)
	def check(self, task):
		return self.exception is None


class CheckTask(Components.Task.PythonTask):
	def work(self):
		if pathExists('/tmp/online-image-version'):
			remove('/tmp/online-image-version')

		file = open('/etc/image-version', 'r')
		lines = file.readlines()
		file.close()
		for x in lines:
			splitted = x.split('=')
			if splitted[0] == "box_type":
				box_type = splitted[1].replace('\n','') # 0 = release, 1 = experimental
			elif splitted[0] == "version":
				version = splitted[1].replace('\n','')
				version = version.split('.')
				version = version[0] + '.' + version[1]

		import urllib
		fd = open('/etc/opkg/all-feed.conf', 'r')
		fileurl = fd.read()
		fd.close()
		if fileurl.find('experimental') < 0:
			sourcefile='http://www.world-of-satellite.com/plugin_feed/feeds/' + version + '/' + box_type + '/image-version'
		else:
			sourcefile='http://www.world-of-satellite.com/plugin_feed/feeds/experimental/' + box_type + '/image-version'
		sourcefile,headers = urllib.urlretrieve(sourcefile)
		rename(sourcefile,'/tmp/online-image-version')

