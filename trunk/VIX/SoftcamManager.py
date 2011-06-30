from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
import Components.Task
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Components.Button import Button
from Components.ScrollLabel import ScrollLabel
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Pixmap import MultiPixmap
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigSubsection, ConfigText, getConfigListEntry, ConfigSelection, ConfigYesNo, ConfigNumber
from Components.Console import Console
from Components.FileList import MultiFileSelectList
from Components.Language import language
from Screens.MessageBox import MessageBox
from Tools.Directories import resolveFilename, SCOPE_LANGUAGE, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from ServiceReference import ServiceReference
from Components.SystemInfo import SystemInfo
from os import path, makedirs, remove, rename, symlink, mkdir, environ, listdir
from shutil import rmtree
from datetime import datetime
from time import localtime, time, strftime, mktime, strftime, sleep
from enigma import eTimer
import gettext

lang = language.getLanguage()
environ["LANGUAGE"] = lang[:2]
print "[SoftcamManager] set language to ", lang[:2]
gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
gettext.textdomain("enigma2")
gettext.bindtextdomain("SoftcamManager", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "ViX/locale"))

softcamautopoller = None

def _(txt):
	t = gettext.dgettext("SoftcamManager", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t

def SoftcamAutostart(reason, session=None, **kwargs):
	"called with reason=1 to during shutdown, with reason=0 at startup?"
	global softcamautopoller
	if reason == 0:
		print "[SoftcamManager] AutoStart Enabled"
		if path.exists('/tmp/SoftcamsDisableCheck'):
			remove('/tmp/SoftcamsDisableCheck')	
		softcamautopoller = SoftcamAutoPoller()
		softcamautopoller.start()
	elif reason == 1:
		# Stop Poller
		if softcamautopoller is not None:
			softcamautopoller.stop()
			softcamautopoller = None

class VIXSoftcamManager(Screen):
	skin = """<screen name="VIXSoftcamManager" position="center,center" size="560,400" title="Softcam Setup" flags="wfBorder">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="lab1" position="40,60" size="170,20" font="Regular; 22" halign="right" zPosition="2" transparent="0" />
		<widget name="list" position="225,60" size="240,100" transparent="0" scrollbarMode="showOnDemand" />
		<widget name="lab2" position="40,165" size="170,30" font="Regular; 22" halign="right" zPosition="2" transparent="0" />
		<widget name="activecam" position="225,166" size="240,100" font="Regular; 20" halign="left" zPosition="2" transparent="0" noWrap="1" />
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Softcam Setup"))
		self['lab1'] = Label(_('Select:'))
		self['lab2'] = Label(_('Active:'))
		self['activecam'] = Label()

		self.sentsingle = ""
		self.selectedFiles = config.softcammanager.softcams_autostart.value
		self.defaultDir = '/usr/softcams/'
		self.emlist = MultiFileSelectList(self.selectedFiles, self.defaultDir, showDirectories = False )
		self["list"] = self.emlist

		self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "TimerEditActions", "MenuActions"],
			{
				'ok': self.keyStart,
				'cancel': self.close,
				'red': self.close,
				'green': self.keyStart,
				'yellow': self.getRestartPID,
				'blue': self.changeSelectionState,
				'log': self.showLog,
				'menu': self.createSetup,
			}, -1)

		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button("")
		self["key_yellow"] = Button("")
		self["key_blue"] = Button(_("Autostart"))

		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.getActivecam)
		self.Console = Console()
		self.showActivecam()
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def createSetup(self):
		self.session.open(VIXSoftcamMenu)

	def selectionChanged(self):
		cams = listdir('/usr/softcams')
		SystemInfo["CCcamInstalled"] = False
		SystemInfo["OScamInstalled"] = False
		for softcam in cams:
			if softcam.lower().startswith('cccam'):
				SystemInfo["CCcamInstalled"] = True
			elif softcam.lower().startswith('oscam'):
				SystemInfo["OScamInstalled"] = True
		if cams:
			current = self["list"].getCurrent()[0]
			selcam = current[0]
			print '[SoftcamManager] Selectedcam: ' + str(selcam)
			if currentactivecam.find(selcam) < 0:
				self["key_green"].setText(_("Start"))
			else:
				self["key_green"].setText(_("Stop"))
			if currentactivecam.find(selcam) < 0:
				self["key_yellow"].setText(_(" "))
			else:
				self["key_yellow"].setText(_("Restart"))

			if current[2] is True:
				self["key_blue"].setText(_("Disable Startup"))
			else:
				self["key_blue"].setText(_("Enable Startup"))
			self.saveSelection()

	def changeSelectionState(self):
		cams = listdir('/usr/softcams')
		if cams:
			self["list"].changeSelectionState()
			self.selectedFiles = self["list"].getSelectedList()

	def saveSelection(self):
		self.selectedFiles = self["list"].getSelectedList()
		config.softcammanager.softcams_autostart.value = self.selectedFiles
		config.softcammanager.softcams_autostart.save()
		config.softcammanager.save()
		config.save()

	def showActivecam(self):
		scanning = _("Wait please while scanning\nfor softcam's...")
		self['activecam'].setText(scanning)
		self.activityTimer.start(10)

	def getActivecam(self):
		self.activityTimer.stop()
		self.Console.ePopen("ps | grep softcams | grep -v 'grep' | sed 's/</ /g' | awk '{print $5}' | awk '{a[$1] = $0} END { for (x in a) { print a[x] } }' | awk -F'[/]' '{print $4}'", self.showActivecam2)

	def showActivecam2(self, result, retval, extra_args):
		global currentactivecam
		if retval == 0:
			currentactivecamtemp = result
			currentactivecam = "".join([s for s in currentactivecamtemp.splitlines(True) if s.strip("\r\n")])
			currentactivecam = currentactivecam.replace('\n',', ')
			print '[SoftcamManager] Active: '  + currentactivecam.replace("\n",", ")
			if path.exists('/tmp/SoftcamsScriptsRunning'):
				SoftcamsScriptsRunning = file('/tmp/SoftcamsScriptsRunning').read()
				SoftcamsScriptsRunning = SoftcamsScriptsRunning.replace('\n',', ')
				currentactivecam = currentactivecam + SoftcamsScriptsRunning
			self['activecam'].setText(currentactivecam)
			self['activecam'].show()
		else:
			print 'RESULT FAILED: ' + str(result)
		self.selectionChanged()

	def keyStart(self):
		cams = listdir('/usr/softcams')
		if cams:
			self.sel = self['list'].getCurrent()[0]
			selectedcam = self.sel[0]
			if currentactivecam.find(selectedcam) < 0:
				if (selectedcam.startswith('CCcam') or selectedcam.startswith('cccam')) and path.exists('/etc/CCcam.cfg') == True:
					if (currentactivecam.find('MGcam') < 0) or (currentactivecam.find('mgcam') < 0):
						self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
					else:
						self.session.open(MessageBox, _("CCcam can't run whilst MGcamd is running"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				elif (selectedcam.startswith('CCcam') or selectedcam.startswith('cccam')) and path.exists('/etc/CCcam.cfg') == False:
					self.session.open(MessageBox, _("No config files found, please setup CCcam first\nin /etc/CCcam.cfg"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				elif (selectedcam.startswith('Hypercam') or selectedcam.startswith('hypercam')) and path.exists('/etc/hypercam.cfg') == True:
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				elif (selectedcam.startswith('Hypercam') or selectedcam.startswith('hypercam')) and path.exists('/etc/hypercam.cfg') == False:
					self.session.open(MessageBox, _("No config files found, please setup Oscam first\nin /etc/hypercam.cfg"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				elif (selectedcam.startswith('Oscam') or selectedcam.startswith('OScam') or selectedcam.startswith('oscam')) and path.exists('/etc/tuxbox/config/oscam.conf') == True:
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				elif (selectedcam.startswith('Oscam') or selectedcam.startswith('OScam') or selectedcam.startswith('oscam')) and path.exists('/etc/tuxbox/config/oscam.conf') == False:
					self.session.open(MessageBox, _("No config files found, please setup Oscam first\nin /etc/tuxbox/config"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				elif (selectedcam.startswith('MGcam') or selectedcam.startswith('mgcam')) and path.exists('/var/keys/mg_cfg') == True:
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				elif (selectedcam.startswith('MGcam') or selectedcam.startswith('mgcam')) and path.exists('/var/keys/mg_cfg') == False:
					if (currentactivecam.find('CCcam') < 0) or (currentactivecam.find('cccam') < 0):
						self.session.open(MessageBox, _("No config files found, please setup MGcamd first\nin /var/keys"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
					else:
						self.session.open(MessageBox, _("MGcamd can't run whilst CCcam is running"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				elif not selectedcam.startswith('CCcam') or selectedcam.startswith('Oscam') or selectedcam.startswith('OScam') or selectedcam.startswith('MGcamd'):
					self.session.open(MessageBox, _("Found none standard softcam, trying to start, this may fail"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			else:
				self.session.openWithCallback(self.showActivecam, VIXStopCam, self.sel[0])

	def getRestartPID(self):
		cams = listdir('/usr/softcams')
		if cams:
			global selectedcam
			self.sel = self['list'].getCurrent()[0]
			selectedcam = self.sel[0]
			self.Console.ePopen("pidof " + selectedcam, self.keyRestart)

	def keyRestart(self, result, retval, extra_args):
		strpos = currentactivecam.find(selectedcam)
		if strpos < 0:
			return
		else:
			if retval == 0:
				stopcam = str(result)
				print '[SoftcamManager] Stopping ' + selectedcam + ' PID ' + stopcam.replace("\n","")
				output = open('/tmp/cam.check.log','a')
				now = datetime.now()
				output.write(now.strftime("%Y-%m-%d %H:%M") + ": Stopping: " + selectedcam + "\n")
				output.close()
				self.Console.ePopen("kill -9 " + stopcam.replace("\n",""))
				sleep(4)
			else:
				print 'RESULT FAILED: ' + str(result)
			if (selectedcam.startswith('CCcam') or selectedcam.startswith('cccam')) and path.exists('/etc/CCcam.cfg') == True:
				if (currentactivecam.find('MGcam') < 0) or (currentactivecam.find('mgcam') < 0):
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				else:
					self.session.open(MessageBox, _("CCcam can't run whilst MGcamd is running"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
			elif (selectedcam.startswith('CCcam') or selectedcam.startswith('cccam')) and path.exists('/etc/CCcam.cfg') == False:
				self.session.open(MessageBox, _("No config files found, please setup CCcam first\nin /etc/CCcam.cfg"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
			elif (selectedcam.startswith('Oscam') or selectedcam.startswith('OScam') or selectedcam.startswith('oscam')) and path.exists('/etc/tuxbox/config/oscam.conf') == True:
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			elif (selectedcam.startswith('Oscam') or selectedcam.startswith('OScam') or selectedcam.startswith('oscam')) and path.exists('/etc/tuxbox/config/oscam.conf') == False:
				if not path.exists('/etc/tuxbox/config'):
					cmd = makedirs('/etc/tuxbox/config')
				self.session.open(MessageBox, _("No config files found, please setup Oscam first\nin /etc/tuxbox/config"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
			elif (selectedcam.startswith('MGcam') or selectedcam.startswith('mgcam')) and path.exists('/var/keys/mg_cfg') == True:
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			elif (selectedcam.startswith('MGcam') or selectedcam.startswith('mgcam')) and path.exists('/var/keys/mg_cfg') == False:
				if (currentactivecam.find('CCcam') < 0) or (currentactivecam.find('cccam') < 0):
					self.session.open(MessageBox, _("No config files found, please setup MGcamd first\nin /var/keys"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				else:
					self.session.open(MessageBox, _("MGcamd can't run whilst CCcam is running"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
			elif not selectedcam.startswith('CCcam') or selectedcam.startswith('Oscam') or selectedcam.startswith('OScam') or selectedcam.startswith('MGcamd'):
				self.session.open(MessageBox, _("Found none stanadard softcam, trying to start, this may fail"), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
		
	def showLog(self):
		self.session.open(VIXSoftcamLog)

	def myclose(self):
		self.close()
			
class VIXStartCam(Screen):
	skin = """<screen name="VIXStartCam" position="center,center" size="484, 150" title="Starting Softcam" flags="wfBorder">
		<widget name="connect" position="217, 0" size="64,64" zPosition="2" pixmaps="ViX_HD/busy/busy1.png,ViX_HD/busy/busy2.png,ViX_HD/busy/busy3.png,ViX_HD/busy/busy4.png,ViX_HD/busy/busy5.png,ViX_HD/busy/busy6.png,ViX_HD/busy/busy7.png,ViX_HD/busy/busy8.png,ViX_HD/busy/busy9.png,ViX_HD/busy/busy9.png,ViX_HD/busy/busy10.png,ViX_HD/busy/busy11.png,ViX_HD/busy/busy12.png,ViX_HD/busy/busy13.png,ViX_HD/busy/busy14.png,ViX_HD/busy/busy15.png,ViX_HD/busy/busy17.png,ViX_HD/busy/busy18.png,ViX_HD/busy/busy19.png,ViX_HD/busy/busy20.png,ViX_HD/busy/busy21.png,ViX_HD/busy/busy22.png,ViX_HD/busy/busy23.png,ViX_HD/busy/busy24.png"  transparent="1" alphatest="blend" />
		<widget name="lab1" position="10, 80" halign="center" size="460, 60" zPosition="1" font="Regular;20" valign="top" transparent="1" />
	</screen>"""
	def __init__(self, session, selectedcam):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Softcam Setup"))
		self['connect'] = MultiPixmap()
		self['lab1'] = Label(_("Please wait while starting\n") + selectedcam + '...')
		global startselectedcam
		startselectedcam = selectedcam
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updatepix)
		self.onShow.append(self.startShow)
		self.onClose.append(self.delTimer)

	def startShow(self):
		self.curpix = 0
		self.count = 0
		self['connect'].setPixmapNum(0)
		if startselectedcam.endswith('.sh'):
			if path.exists('/tmp/SoftcamsScriptsRunning'):
				data = file('/tmp/SoftcamsScriptsRunning').read()
				if data.find(startselectedcam) >= 0:
					file('/tmp/SoftcamsScriptsRunning.tmp', 'w').writelines([l for l in file('/tmp/SoftcamsScriptsRunning').readlines() if startselectedcam not in l])
					rename('/tmp/SoftcamsScriptsRunning.tmp','/tmp/SoftcamsScriptsRunning')
				elif data.find(startselectedcam) < 0:
					fileout = open('/tmp/SoftcamsScriptsRunning', 'a')
					line = startselectedcam + '\n'
					fileout.write(line)
					fileout.close()
			else:
				fileout = open('/tmp/SoftcamsScriptsRunning', 'w')
				line = startselectedcam + '\n'
				fileout.write(line)
				fileout.close()
			print '[SoftcamManager] Starting ' + startselectedcam
			output = open('/tmp/cam.check.log','a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Starting " + startselectedcam + "\n")
			output.close()
			self.Console.ePopen('/usr/softcams/' + startselectedcam + ' start' )
		else:
			if path.exists('/tmp/SoftcamsDisableCheck'):
				data = file('/tmp/SoftcamsDisableCheck').read()
				if data.find(startselectedcam) >= 0:
					output = open('/tmp/cam.check.log','a')
					now = datetime.now()
					output.write(now.strftime("%Y-%m-%d %H:%M") + ": Initialised timed check for " + stopselectedcam + "\n")
					output.close()
					file('/tmp/SoftcamsDisableCheck.tmp', 'w').writelines([l for l in file('/tmp/SoftcamsDisableCheck').readlines() if startselectedcam not in l])
					rename('/tmp/SoftcamsDisableCheck.tmp','/tmp/SoftcamsDisableCheck')
			print '[SoftcamManager] Starting ' + startselectedcam
			output = open('/tmp/cam.check.log','a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Starting " + startselectedcam + "\n")
			output.close()
			if (startselectedcam.startswith('Hypercam') or startselectedcam.startswith('hypercam')):
				self.Console.ePopen('/usr/softcams/' + startselectedcam + ' -c /etc/hypercam.cfg')
			elif (startselectedcam.startswith('Oscam') or startselectedcam.startswith('OScam') or startselectedcam.startswith('oscam')):
				self.Console.ePopen('/usr/softcams/' + startselectedcam + ' -b')
			elif startselectedcam.startswith('Gbox') or startselectedcam.startswith('gbox'):
				self.Console.ePopen('/usr/softcams/' + startselectedcam)
				sleep(3)
				self.Console.ePopen('start-stop-daemon --start --quiet --background --exec /usr/bin/gbox')
			else:
				self.Console.ePopen('/usr/softcams/' + startselectedcam)
		self.activityTimer.start(1)

	def updatepix(self):
		self.activityTimer.stop()
		if (startselectedcam.startswith('CCcam') or startselectedcam.startswith('cccam')):
			if self.curpix > 23:
				self.curpix = 0
			if self.count > 120:
				self.curpix = 23
			self['connect'].setPixmapNum(self.curpix)
			if self.count == 120: # timer on screen
				self.hide()
				self.close()
			self.activityTimer.start(120) # cycle speed
			self.curpix += 1
			self.count += 1
		else:
			if self.curpix > 23:
				self.curpix = 0
			if self.count > 23:
				self.curpix = 0
			self['connect'].setPixmapNum(self.curpix)
			if self.count == 25: # timer on screen
				self.hide()
				self.close()
			self.activityTimer.start(120) # cycle speed
			self.curpix += 1
			self.count += 1

	def delTimer(self):
		del self.activityTimer

class VIXStopCam(Screen):
	skin = """<screen name="VIXStopCam" position="center,center" size="484, 150" title="Stopping Softcam" flags="wfBorder">
		<widget name="connect" position="217, 0" size="64,64" zPosition="2" pixmaps="ViX_HD/busy/busy1.png,ViX_HD/busy/busy2.png,ViX_HD/busy/busy3.png,ViX_HD/busy/busy4.png,ViX_HD/busy/busy5.png,ViX_HD/busy/busy6.png,ViX_HD/busy/busy7.png,ViX_HD/busy/busy8.png,ViX_HD/busy/busy9.png,ViX_HD/busy/busy9.png,ViX_HD/busy/busy10.png,ViX_HD/busy/busy11.png,ViX_HD/busy/busy12.png,ViX_HD/busy/busy13.png,ViX_HD/busy/busy14.png,ViX_HD/busy/busy15.png,ViX_HD/busy/busy17.png,ViX_HD/busy/busy18.png,ViX_HD/busy/busy19.png,ViX_HD/busy/busy20.png,ViX_HD/busy/busy21.png,ViX_HD/busy/busy22.png,ViX_HD/busy/busy23.png,ViX_HD/busy/busy24.png"  transparent="1" alphatest="blend" />
		<widget name="lab1" position="10, 80" halign="center" size="460, 60" zPosition="1" font="Regular;20" valign="top" transparent="1" />
	</screen>"""
	def __init__(self, session, selectedcam):
		Screen.__init__(self, session)
		global stopselectedcam
		stopselectedcam = selectedcam
		Screen.setTitle(self, _("Softcam Setup"))
		self['connect'] = MultiPixmap()
		self['lab1'] = Label(_("Please wait while stopping\n") + selectedcam + '...')
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updatepix)
		self.onShow.append(self.getStopPID)
		self.onClose.append(self.delTimer)
		
	def getStopPID(self):
		if stopselectedcam.endswith('.sh'):
			self.curpix = 0
			self.count = 0
			self['connect'].setPixmapNum(0)
			print '[SoftcamManager] Stopping ' + stopselectedcam
			output = open('/tmp/cam.check.log','a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Stopping " + stopselectedcam + "\n")
			output.close()
			self.Console.ePopen('/usr/softcams/' + stopselectedcam + ' stop' )
			if path.exists('/tmp/SoftcamsScriptsRunning'):
				remove('/tmp/SoftcamsScriptsRunning')
			if path.exists('/etc/SoftcamsAutostart'):
				data = file('/etc/SoftcamsAutostart').read()
				finddata = data.find(stopselectedcam)
				if data.find(stopselectedcam) >= 0:
					print '[SoftcamManager] Temporarily disabled timed check for ' + stopselectedcam
					output = open('/tmp/cam.check.log','a')
					now = datetime.now()
					output.write(now.strftime("%Y-%m-%d %H:%M") + ": Temporarily disabled timed check for " + stopselectedcam + "\n")
					output.close()
					fileout = open('/tmp/SoftcamsDisableCheck', 'a')
					line = stopselectedcam + '\n'
					fileout.write(line)
					fileout.close()
			self.activityTimer.start(1)
		else:
			if stopselectedcam.find("Oscam") >= 0 and currentactivecam.find("01_") >= 0:
				self.Console.ePopen("pidof " + stopselectedcam.replace("Oscam","01_Oscam"), self.startShow)
			elif stopselectedcam.find("oscam") >= 0 and currentactivecam.find("01_") >= 0:
				self.Console.ePopen("pidof " + stopselectedcam.replace("oscam","01_oscam"), self.startShow)
			else:
				self.Console.ePopen("pidof " + stopselectedcam, self.startShow)

	def startShow(self, result, retval, extra_args):
		if retval == 0:
			self.curpix = 0
			self.count = 0
			self['connect'].setPixmapNum(0)
			stopcam = str(result)
			if path.exists('/etc/SoftcamsAutostart'):
				data = file('/etc/SoftcamsAutostart').read()
				finddata = data.find(stopselectedcam)
				if data.find(stopselectedcam) >= 0:
					print '[SoftcamManager] Temporarily disabled timed check for ' + stopselectedcam
					output = open('/tmp/cam.check.log','a')
					now = datetime.now()
					output.write(now.strftime("%Y-%m-%d %H:%M") + ": Temporarily disabled timed check for " + stopselectedcam + "\n")
					output.close()
					fileout = open('/tmp/SoftcamsDisableCheck', 'a')
					line = stopselectedcam + '\n'
					fileout.write(line)
					fileout.close()
			print '[SoftcamManager] Stopping ' + stopselectedcam + ' PID ' + stopcam.replace("\n","")
			output = open('/tmp/cam.check.log','a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Stopping " + stopselectedcam + "\n")
			output.close()
			self.Console.ePopen("kill -9 " + stopcam.replace("\n",""))
			self.activityTimer.start(1)

	def updatepix(self):
		self.activityTimer.stop()
		if self.curpix > 23:
			self.curpix = 0
		if self.count > 23:
			self.curpix = 0
		self['connect'].setPixmapNum(self.curpix)
		if self.count == 25: # timer on screen
			self.hide()
			self.close()
		self.activityTimer.start(120) # cycle speed
		self.curpix += 1
		self.count += 1

	def delTimer(self):
		del self.activityTimer

class VIXSoftcamLog(Screen):
	skin = """
<screen name="VIXSoftcamLog" position="center,center" size="560,400" title="Softcam Manager Log" >
	<widget name="list" position="0,0" size="560,400" font="Regular;14" />
</screen>"""
	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		self.skinName = "VIXSoftcamLog"
		if path.exists('/var/volatile/tmp/cam.check.log'):
			softcamlog = file('/var/volatile/tmp/cam.check.log').read()
		else:
			softcamlog = ""
		self["list"] = ScrollLabel(str(softcamlog))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
		{
			"cancel": self.cancel,
			"ok": self.cancel,
			"up": self["list"].pageUp,
			"down": self["list"].pageDown
		}, -2)

	def cancel(self):
		self.close()

class VIXSoftcamMenu(ConfigListScreen, Screen):
	skin = """
		<screen name="VIXSoftcamMenu" position="center,center" size="500,285" title="Softcam Menu">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="config" position="10,45" size="480,250" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.skin = VIXSoftcamMenu.skin
		self.skinName = "VIXSoftcamMenu"
		Screen.setTitle(self, _("Softcam Setup"))
		self.onChangedEntry = [ ]

		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self.createSetup()
		
		self["actions"] = ActionMap(["SetupActions"],
		{
		  "cancel": self.keyCancel,
		  "save": self.keySaveNew
		}, -2)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))

	def createSetup(self):
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Enable Auto Timer Check ?"), config.softcammanager.softcamtimerenabled))
		if config.softcammanager.softcamtimerenabled.value:
			self.list.append(getConfigListEntry(_("Check every (mins)"), config.softcammanager.softcamtimer))
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
		for x in self["config"].list:
			x[1].save()
		if config.softcammanager.softcamtimerenabled.value:
			print "[SoftcamManager] Timer Check Enabled"
			softcamautopoller.start()
		else:
			print "[SoftcamManager] Timer Check Disabled"
			softcamautopoller.stop()
		self.close()

	def keyCancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close()

class SoftcamCheckTask(Components.Task.PythonTask):
	def setup(self, autostartcams):
		self.autostartcams = autostartcams

	def work(self):
		self.Console = Console()
		if path.exists('/tmp/cam.check.log'):
			if path.getsize('/tmp/cam.check.log') > 40000:
				fh = open('/tmp/cam.check.log', 'rb+')
				fh.seek(-40000, 2)
				data = fh.read()
				fh.seek(0) # rewind
				fh.write(data)
				fh.truncate()
				fh.close()

		if path.exists('/etc/CCcam.cfg'):
			f = open('/etc/CCcam.cfg', 'r')
			logwarn = ""
			for line in f.readlines():
				if line.find('LOG WARNINGS') != -1:
					parts = line.strip().split()
					logwarn = parts[2]
					if logwarn.find(':') >=0:
						logwarn = logwarn.replace(':','')
					if logwarn == '':
						logwarn = parts[3]
				else:
					logwarn = ""
			if path.exists(logwarn):
				if path.getsize(logwarn) > 40000:
					fh = open(logwarn, 'rb+')
					fh.seek(-40000, 2)
					data = fh.read()
					fh.seek(0) # rewind
					fh.write(data)
					fh.truncate()
					fh.close()

		for softcamcheck in self.autostartcams:
			softcamcheck = softcamcheck.replace("/usr/softcams/","")
			softcamcheck = softcamcheck.replace("\n","")
			if softcamcheck.endswith('.sh'):
				if path.exists('/tmp/SoftcamsDisableCheck'):
					data = file('/tmp/SoftcamsDisableCheck').read()
				else:
					data = ''
				if data.find(softcamcheck) < 0:
					if path.exists('/tmp/SoftcamsScriptsRunning'):
						data = file('/tmp/SoftcamsScriptsRunning').read()
						if data.find(softcamcheck) < 0:
							fileout = open('/tmp/SoftcamsScriptsRunning', 'a')
							line = softcamcheck + '\n'
							fileout.write(line)
							fileout.close()
							print '[SoftcamManager] Starting ' + softcamcheck
							self.Console.ePopen('/usr/softcams/' + softcamcheck + ' start' )
					else:
						fileout = open('/tmp/SoftcamsScriptsRunning', 'w')
						line = softcamcheck + '\n'
						fileout.write(line)
						fileout.close()
						print '[SoftcamManager] Starting ' + softcamcheck
						self.Console.ePopen('/usr/softcams/' + softcamcheck + ' start' )
			else:
				if path.exists('/tmp/SoftcamsDisableCheck'):
					data = file('/tmp/SoftcamsDisableCheck').read()
				else:
					data = ''
				if data.find(softcamcheck) < 0:
					import process
					p = process.ProcessList()
					softcamcheck_process = str(p.named(softcamcheck)).strip('[]')
					if softcamcheck_process != "":
						print '[SoftcamManager] ' + softcamcheck + ' already running'
						output = open('/tmp/cam.check.log','a')
						now = datetime.now()
						output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " running OK\n")
						output.close()
						if softcamcheck.startswith('Oscam') or softcamcheck.startswith('OScam') or softcamcheck.startswith('oscam'):
							port = ''
							f = open('/etc/tuxbox/config/oscam.conf', 'r')
							for line in f.readlines():
								if line.find('httpport') != -1:
									parts = line.strip().split()
									port = parts[2]
									if port.find('=') >=0:
										port = port.replace('=','')
									if port == '':
										port = parts[3]
							f.close()
							print '[SoftcamManager] Checking if ' + softcamcheck + ' is frozen'
							if port == "":
								port="16000"
							self.Console.ePopen("wget http://127.0.0.1:" + port + "/status.html 2> /tmp/frozen")
							sleep(2)
							frozen = file('/tmp/frozen').read()
							if frozen.find('Unauthorized') or frozen.find('100%')>=0:
								print '[SoftcamManager] ' + softcamcheck + ' is responding like it should'
								output = open('/tmp/cam.check.log','a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is responding like it should\n")
								output.close()
							elif frozen.find('Unauthorized') <0:
								print '[SoftcamManager] ' + softcamcheck + ' is frozen, Restarting...'
								output = open('/tmp/cam.check.log','a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is frozen, Restarting...\n")
								output.close()
								print '[SoftcamManager] Stopping ' + softcamcheck
								output = open('/tmp/cam.check.log','a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStopping: " + softcamcheck + "\n")
								output.close()
								self.Console.ePopen("killall -9 " + softcamcheck)
								sleep(1)
								self.Console.ePopen("ps | grep softcams | grep -v grep | awk 'NR==1' | awk '{print $5}'| awk  -F'[/]' '{print $4}' > /tmp/oscamRuningCheck.tmp")
								sleep(2)
								cccamcheck_process = file('/tmp/oscamRuningCheck.tmp').read()
								cccamcheck_process = cccamcheck_process.replace("\n","")
								if cccamcheck_process.find('cccam') >= 0 or cccamcheck_process.find('CCcam') >= 0:
									try:
										print '[SoftcamManager] Stopping ', cccamcheck_process
										output = open('/tmp/cam.check.log','a')
										now = datetime.now()
										output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStopping: " + cccamcheck_process + "\n")
										output.close()
										self.Console.ePopen("killall -9 /usr/softcams/" + str(cccamcheck_process))
									except:
										pass
								print '[SoftcamManager] Starting ' + softcamcheck
								output = open('/tmp/cam.check.log','a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStarting: " + softcamcheck + "\n")
								output.close()
								self.Console.ePopen('/usr/softcams/' + softcamcheck + ' -b')
								sleep(10)
							remove('/tmp/frozen')

						elif softcamcheck.startswith('CCcam') or softcamcheck.startswith('cccam'):
							allow = 'notset'
							port = ''
							f = open('/etc/CCcam.cfg', 'r')
							for line in f.readlines():
								if line.find('ALLOW TELNETINFO') != -1:
									parts = line.strip().split()
									if parts[1].startswith('TELNETINFO='):
										allow = parts[1].replace('TELNETINFO=','')
									else:
										allow = parts[2]
									if allow.find(':') >=0:
										allow = allow.replace(':','')
									if allow == '' or allow == '=':
										allow = parts[3]
								if line.find('TELNETINFO USERNAME') != -1:
									parts = line.strip().split()
									if parts[1].startswith('USERNAME='):
										username = parts[1].replace('USERNAME=','')
									else:
										username = parts[2]
									if username.find(':') >=0:
										username = username.replace(':','')
									if username == '' or allow == '=':
										username = parts[3]
								if line.find('TELNETINFO PASSWORD') != -1:
									parts = line.strip().split()
									if parts[1].startswith('PASSWORD='):
										password = parts[1].replace('PASSWORD=','')
									else:
										password = parts[2]
									if password.find(':') >=0:
										password = password.replace(':','')
									if password == '' or allow == '=':
										password = parts[3]
								if line.find('TELNETINFO LISTEN PORT') != -1:
									parts = line.strip().split()
									if parts[2].startswith('PORT='):
										port = parts[2].replace('PORT=','')
									else:
										port = parts[3]
									if port.find(':') >=0:
										port = port.replace(':','')
									if port == '' or allow == '=':
										port = parts[4]
							f.close()
							if allow.find('YES') >= 0 or allow.find('yes') >= 0:
								print '[SoftcamManager] Checking if ' + softcamcheck + ' is frozen'
								if port == "":
									port="16000"
								self.Console.ePopen("echo info|nc 127.0.0.1 " + port + " | grep Welcome | awk '{print $1}' > /tmp/frozen")
								sleep(2)
								frozen = file('/tmp/frozen').read()
								if frozen.find('Welcome') >=0:
									print '[SoftcamManager] ' + softcamcheck + ' is responding like it should'
									output = open('/tmp/cam.check.log','a')
									now = datetime.now()
									output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is responding like it should\n")
									output.close()
								elif frozen.find('Welcome') <0:
									print '[SoftcamManager] ' + softcamcheck + ' is frozen, Restarting...'
									output = open('/tmp/cam.check.log','a')
									now = datetime.now()
									output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is frozen, Restarting...\n")
									output.close()
									print '[SoftcamManager] Stopping ' + softcamcheck
									self.Console.ePopen("killall -9 " + softcamcheck)
									sleep(1)
									print '[SoftcamManager] Starting ' + softcamcheck
									self.Console.ePopen('/usr/softcams/' + softcamcheck)
								remove('/tmp/frozen')
							elif allow.find('NO') >= 0 or allow.find('no') >= 0:
								print '[SoftcamManager] Telnet info not allowed, can not check if frozen'
								output = open('/tmp/cam.check.log','a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ":  Telnet info not allowed, can not check if frozen,\n\tplease enable 'ALLOW TELNETINFO = YES'\n")
								output.close()
							else:
								print "[SoftcamManager] Telnet info not setup, please enable 'ALLOW TELNETINFO = YES'"
								output = open('/tmp/cam.check.log','a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ":  Telnet info not setup, can not check if frozen,\n\tplease enable 'ALLOW TELNETINFO = YES'\n")
								output.close()

					elif softcamcheck_process == "":
						output = open('/tmp/cam.check.log','a')
						now = datetime.now()
						output.write(now.strftime("%Y-%m-%d %H:%M") + ": Couldn't find " + softcamcheck + " running, Starting " + softcamcheck + "\n")
						output.close()
						if softcamcheck.startswith('Oscam') or softcamcheck.startswith('OScam') or softcamcheck.startswith('oscam'):
							self.Console.ePopen("ps | grep softcams | grep -v grep | awk 'NR==1' | awk '{print $5}'| awk  -F'[/]' '{print $4}' > /tmp/cccamRuningCheck.tmp")
							sleep(2)
							cccamcheck_process = file('/tmp/cccamRuningCheck.tmp').read()
							cccamcheck_process = cccamcheck_process.replace("\n","")
							if cccamcheck_process.find('cccam') >= 0 or cccamcheck_process.find('CCcam') >= 0:
								try:
									print '[SoftcamManager] Stopping ', cccamcheck_process
									output = open('/tmp/cam.check.log','a')
									now = datetime.now()
									output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStopping: " + cccamcheck_process + "\n")
									output.close()
									self.Console.ePopen("killall -9 /usr/softcams/" + str(cccamcheck_process))
								except:
									pass
							self.Console.ePopen('/usr/softcams/' + softcamcheck + " -b")
							sleep(10)
							remove('/tmp/cccamRuningCheck.tmp')
						elif softcamcheck.startswith('Sbox') or softcamcheck.startswith('sbox'):
							self.Console.ePopen('/usr/softcams/' + softcamcheck)
							sleep(7)
						elif softcamcheck.startswith('Gbox') or softcamcheck.startswith('gbox'):
							self.Console.ePopen('/usr/softcams/' + softcamcheck)
							sleep(3)
							self.Console.ePopen('start-stop-daemon --start --quiet --background --exec /usr/bin/gbox')
						else:
							self.Console.ePopen('/usr/softcams/' + softcamcheck)

class SoftcamAutoPoller:
	"""Automatically Poll SoftCam"""
	def __init__(self):
		# Init Timer
		if not path.exists('/etc/keys'):
			mkdir('/etc/keys', 0755)
		if not path.exists('/etc/tuxbox/config'):
			mkdir('/etc/tuxbox/config', 0755)
		if not path.exists('/var/tuxbox'):
			symlink('/etc/tuxbox', '/var/tuxbox')
		if not path.exists('/var/keys'):
			symlink('/etc/keys', '/var/keys')
		if not path.exists('/usr/keys'):
			symlink('/etc/keys', '/usr/keys')
		if not path.exists('/etc/scce'):
			mkdir('/etc/scce', 0755)
		if not path.exists('/var/scce'):
			symlink('/etc/scce', '/var/scce')
		if not path.exists('/usr/softcams'):
			mkdir('/usr/softcams', 0755)
		self.timer = eTimer()

	def start(self):
		if self.softcam_check not in self.timer.callback:
			self.timer.callback.append(self.softcam_check)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.softcam_check in self.timer.callback:
			self.timer.callback.remove(self.softcam_check)
		self.timer.stop()

	def softcam_check(self):
		now = int(time())
		print "[SoftcamManager] Poll occured at", strftime("%c", localtime(now))
		if path.exists('/tmp/SoftcamRuningCheck.tmp'):
			remove('/tmp/SoftcamRuningCheck.tmp')

		if config.softcammanager.softcams_autostart:
			autostartcams = config.softcammanager.softcams_autostart.value
			name = _("SoftcamCheck")
			job = Components.Task.Job(name)
			task = SoftcamCheckTask(job, name)
			task.setup(autostartcams)
			Components.Task.job_manager.AddJob(job)

		if config.softcammanager.softcamtimerenabled.value:
			print "[SoftcamManager] Timer Check Enabled"
			output = open('/tmp/cam.check.log','a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Timer Check Enabled\n")
			output.close()
			self.timer.startLongTimer(config.softcammanager.softcamtimer.value * 60)
		else:
			output = open('/tmp/cam.check.log','a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Timer Check Disabled\n")
			output.close()
			print "[SoftcamManager] Timer Check Disabled"
			softcamautopoller.stop()

