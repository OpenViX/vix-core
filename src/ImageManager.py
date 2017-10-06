# for localized messages
from boxbranding import getBoxType, getImageType, getImageDistro, getImageVersion, getImageBuild, getImageDevBuild, getImageFolder, getImageFileSystem, getBrandOEM, getMachineBrand, getMachineName, getMachineBuild, getMachineMake, getMachineMtdRoot, getMachineRootFile, getMachineMtdKernel, getMachineKernelFile, getMachineMKUBIFS, getMachineUBINIZE
from os import path, system, mkdir, makedirs, listdir, remove, rename, statvfs, chmod, walk, symlink, unlink
from shutil import rmtree, move, copy
from time import localtime, time, strftime, mktime

from enigma import eTimer

from . import _, PluginLanguageDomain
import Components.Task
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock
from Components.Harddisk import harddiskmanager, getProcMounts
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Screens.Setup import Setup
from Components.Console import Console
from Screens.Console import Console as ScreenConsole

from Screens.TaskView import JobView
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Tools.Notifications import AddPopupWithCallback
import Tools.CopyFiles

import urllib

RAMCHEKFAILEDID = 'RamCheckFailedNotification'

hddchoises = []
for p in harddiskmanager.getMountedPartitions():
	if path.exists(p.mountpoint):
		d = path.normpath(p.mountpoint)
		if p.mountpoint != '/':
			hddchoises.append((p.mountpoint, d))
config.imagemanager = ConfigSubsection()
defaultprefix = getImageDistro() + '-' + getBoxType()
config.imagemanager.folderprefix = ConfigText(default=defaultprefix, fixed_size=False)
config.imagemanager.backuplocation = ConfigSelection(choices=hddchoises)
config.imagemanager.schedule = ConfigYesNo(default=False)
config.imagemanager.scheduletime = ConfigClock(default=0)  # 1:00
config.imagemanager.repeattype = ConfigSelection(default="daily", choices=[("daily", _("Daily")), ("weekly", _("Weekly")), ("monthly", _("30 Days"))])
config.imagemanager.backupretry = ConfigNumber(default=30)
config.imagemanager.backupretrycount = NoSave(ConfigNumber(default=0))
config.imagemanager.nextscheduletime = NoSave(ConfigNumber(default=0))
config.imagemanager.restoreimage = NoSave(ConfigText(default=getBoxType(), fixed_size=False))
config.imagemanager.autosettingsbackup = ConfigYesNo(default = True)
config.imagemanager.query = ConfigYesNo(default=True)
config.imagemanager.lastbackup = ConfigNumber(default=0)
config.imagemanager.number_to_keep = ConfigNumber(default=0)

autoImageManagerTimer = None

if path.exists(config.imagemanager.backuplocation.value + 'imagebackups/imagerestore'):
	try:
		rmtree(config.imagemanager.backuplocation.value + 'imagebackups/imagerestore')
	except:
		pass

def ImageManagerautostart(reason, session=None, **kwargs):
	"""called with reason=1 to during /sbin/shutdown.sysvinit, with reason=0 at startup?"""
	global autoImageManagerTimer
	global _session
	now = int(time())
	if reason == 0:
		print "[ImageManager] AutoStart Enabled"
		if session is not None:
			_session = session
			if autoImageManagerTimer is None:
				autoImageManagerTimer = AutoImageManagerTimer(session)
	else:
		if autoImageManagerTimer is not None:
			print "[ImageManager] Stop"
			autoImageManagerTimer.stop()

class VIXImageManager(Screen):
	skin = """<screen name="VIXImageManager" position="center,center" size="560,400" title="Image Manager">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<ePixmap pixmap="skin_default/buttons/key_menu.png" position="0,40" size="35,25" alphatest="blend" transparent="1" zPosition="3"/>
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand"/>
		<widget name="backupstatus" position="10,370" size="400,30" font="Regular;20" zPosition="5"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle = _("Image manager")
		self.menu_path = menu_path
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			condtext = ""
			if self.menu_path and not self.menu_path.endswith(' / '):
				condtext = self.menu_path + " >"
			elif self.menu_path:
				condtext = self.menu_path[:-3] + " >"
			self["menu_path_compressed"] = StaticText(condtext)
			self.menu_path += screentitle + ' / '
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self['lab1'] = Label()
		self["backupstatus"] = Label()
		if getImageFileSystem().replace(' ','') not in ('tar.bz2', 'hd-emmc'):
			self["key_blue"] = Button(_("Flash"))
		else:
			self["key_blue"] = Button("")
		self["key_green"] = Button()
		self["key_yellow"] = Button(_("Downloads"))
		self["key_red"] = Button(_("Delete"))

		self.BackupRunning = False
		self.onChangedEntry = []
		self.oldlist = None
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.backupRunning)
		self.activityTimer.start(10)

		self.Console = Console()

		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next backup: ")
		self["backupstatus"].setText(str(backuptext))
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary

		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		desc = self["backupstatus"].text
		if item:
			name = item
		else:
			name = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def backupRunning(self):
		self.populate_List()
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image manager")):
				self.BackupRunning = True
		if self.BackupRunning:
			self["key_green"].setText(_("View progress"))
		else:
			self["key_green"].setText(_("New backup"))
		self.activityTimer.startLongTimer(5)

	def refreshUp(self):
		self.refreshList()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveUp)

	def refreshDown(self):
		self.refreshList()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveDown)

	def refreshList(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if fil.endswith('.zip') or path.isdir(path.join(self.BackupDirectory, fil)):
				self.emlist.append(fil)
		self.emlist.sort()
		self.emlist.reverse()
		self["list"].setList(self.emlist)
		self["list"].show()

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100 * job.progress / float(job.end)))

	def showJobView(self, job):
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, backgroundable=False, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def populate_List(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if path.exists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				if p.mountpoint != '/':
					imparts.append((p.mountpoint, d))
		config.imagemanager.backuplocation.setChoices(imparts)

		if config.imagemanager.backuplocation.value.endswith('/'):
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value[:-1]
		else:
			mount = config.imagemanager.backuplocation.value + '/', config.imagemanager.backuplocation.value
		hdd = '/media/hdd/', '/media/hdd'
		if mount not in config.imagemanager.backuplocation.choices.choices:
			if hdd in config.imagemanager.backuplocation.choices.choices:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "HelpActions"],
											  {
											  'cancel': self.close,
											  'red': self.keyDelete,
											  'green': self.GreenPressed,
											  'yellow': self.doDownload,
											  "menu": self.createSetup,
											  "up": self.refreshUp,
											  "down": self.refreshDown,
											  "displayHelp": self.doDownload,
											  }, -1)
				if getImageFileSystem().replace(' ','') not in ('tar.bz2', 'hd-emmc'):
					self['restoreaction'] = ActionMap(['ColorActions', 'OkCancelActions'],
												  {
												  "ok": self.keyResstore,
												  'blue': self.keyResstore,
												  }, -1)

				self.BackupDirectory = '/media/hdd/imagebackups/'
				config.imagemanager.backuplocation.value = '/media/hdd/'
				config.imagemanager.backuplocation.save()
				self['lab1'].setText(_("The chosen location does not exist, using /media/hdd") + "\n" + _("Select an image to flash:"))
			else:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
											  {
											  'cancel': self.close,
											  "menu": self.createSetup,
											  }, -1)

				self['lab1'].setText(_("Device: None available") + "\n" + _("Select an image to flash:"))
		else:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "HelpActions"],
										  {
										  'cancel': self.close,
										  'red': self.keyDelete,
										  'green': self.GreenPressed,
										  'yellow': self.doDownload,
										  "menu": self.createSetup,
										  "up": self.refreshUp,
										  "down": self.refreshDown,
										  "displayHelp": self.doDownload,
										  }, -1)
			if getImageFileSystem().replace(' ','') not in ('tar.bz2', 'hd-emmc'):
				self['restoreaction'] = ActionMap(['ColorActions', 'OkCancelActions'],
											  {
											  "ok": self.keyResstore,
											  'blue': self.keyResstore,
											  }, -1)

			self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
			s = statvfs(config.imagemanager.backuplocation.value)
			free = (s.f_bsize * s.f_bavail) / (1024 * 1024)
			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + ' ' + _('Free space:') + ' ' + str(free) + _('MB') + "\n" + _("Select an image to flash:"))

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-swapfile_backup')
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-swapfile_backup')
			self.refreshList()
		except:
			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + "\n" + _("there is a problem with this device, please reformat it and try again."))

	def createSetup(self):
		self.session.openWithCallback(self.setupDone, Setup, 'viximagemanager', 'SystemPlugins/ViX', self.menu_path, PluginLanguageDomain)

	def doDownload(self):
		self.session.openWithCallback(self.populate_List, ImageManagerDownload, self.menu_path, self.BackupDirectory)

	def setupDone(self, test=None):
		if config.imagemanager.folderprefix.value == '':
			config.imagemanager.folderprefix.value = defaultprefix
			config.imagemanager.folderprefix.save()
		self.populate_List()
		self.doneConfiguring()

	def doneConfiguring(self):
		now = int(time())
		if config.imagemanager.schedule.value:
			if autoImageManagerTimer is not None:
				print "[ImageManager] Backup Schedule Enabled at", strftime("%c", localtime(now))
				autoImageManagerTimer.backupupdate()
		else:
			if autoImageManagerTimer is not None:
				global BackupTime
				BackupTime = 0
				print "[ImageManager] Backup Schedule Disabled at", strftime("%c", localtime(now))
				autoImageManagerTimer.backupstop()
		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next backup: ")
		self["backupstatus"].setText(str(backuptext))

	def keyDelete(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to delete this image backup:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDelete, MessageBox, message, MessageBox.TYPE_YESNO, default=False)
			ybox.setTitle(_("Remove confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to delete."), MessageBox.TYPE_INFO, timeout=10)

	def doDelete(self, answer):
		if answer is True:
			self.sel = self['list'].getCurrent()
			self["list"].instance.moveSelectionTo(0)
			if self.sel.endswith('.zip'):
				remove(self.BackupDirectory + self.sel)
			else:
				rmtree(self.BackupDirectory + self.sel)
		self.populate_List()

	def GreenPressed(self):
		backup = None
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image manager")):
				backup = job
				self.BackupRunning = True
		if self.BackupRunning and backup:
			self.showJobView(backup)
		else:
			self.keyBackup()

	def keyBackup(self):
		message = _("Do you want to create a full image backup?\nThis can take about 6 minutes to complete.")
		ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Backup confirmation"))

	def doBackup(self, answer):
		if answer is True:
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			self.BackupRunning = True
			self["key_green"].setText(_("View progress"))
			self["key_green"].show()
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Image manager")):
					break
			self.showJobView(job)

	def doSettingsBackup(self):
		from Plugins.SystemPlugins.ViX.BackupManager import BackupFiles
		self.BackupFiles = BackupFiles(self.session, False, True)
		Components.Task.job_manager.AddJob(self.BackupFiles.createBackupJob())
		Components.Task.job_manager.in_background = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_('Backup manager')):
				break
		self.session.openWithCallback(self.keyResstore3, JobView, job,  cancelable = False, backgroundable = False, afterEventChangeable = False, afterEvent="close")

	def keyResstore(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to flash this image:\n ") + self.sel
			ybox = self.session.openWithCallback(self.keyResstore2, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Restore confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to flash."), MessageBox.TYPE_INFO, timeout=10)

	def keyResstore2(self, answer):
		if answer:
			if config.imagemanager.autosettingsbackup.value:
				self.doSettingsBackup()
			else:
				self.keyResstore3()

	def keyResstore3(self, val = None):
		self.restore_infobox = self.session.open(MessageBox, _("Please wait while the flash prepares"), MessageBox.TYPE_INFO, timeout=60, enable_input=False)
		self.TEMPDESTROOT = self.BackupDirectory + 'imagerestore'
		if self.sel.endswith('.zip'):
			if not path.exists(self.TEMPDESTROOT):
				mkdir(self.TEMPDESTROOT, 0755)
			self.Console.ePopen('unzip -o %s%s -d %s' % (self.BackupDirectory, self.sel, self.TEMPDESTROOT), self.keyResstore4)
		else:
			self.TEMPDESTROOT = self.BackupDirectory + self.sel
			self.keyResstore4(0, 0)

	def keyResstore4(self, result, retval, extra_args=None):
		if retval == 0:
			kernelMTD = getMachineMtdKernel()
			rootMTD = getMachineMtdRoot()
			MAINDEST = '%s/%s' % (self.TEMPDESTROOT,getImageFolder())
			CMD = '/usr/bin/ofgwrite -r%s -k%s %s/' % (rootMTD, kernelMTD, MAINDEST)
			config.imagemanager.restoreimage.setValue(self.sel)
			print '[ImageManager] running commnd:',CMD
			self.Console.ePopen(CMD, self.ofgwriteResult)

# We'll only arrive at this function if the ofgwrite failed.
# If it succeeded it will have rebooted the system.
# This displays the errors to the user, and puts them into any debug
# log, for reporting.
#
	def ofgwriteResult(self, result, retval, extra_args=None):
		if retval != 0:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("ofgwrite error (also sent to any debug log):\n%s") % result, MessageBox.TYPE_INFO, timeout=20)
			print "[ImageManager] OFGWriteResult failed:\n", result

class AutoImageManagerTimer:
	def __init__(self, session):
		self.session = session
		self.backuptimer = eTimer()
		self.backuptimer.callback.append(self.BackuponTimer)
		self.backupactivityTimer = eTimer()
		self.backupactivityTimer.timeout.get().append(self.backupupdatedelay)
		now = int(time())
		global BackupTime
		if config.imagemanager.schedule.value:
			print "[ImageManager] Backup Schedule Enabled at ", strftime("%c", localtime(now))
			if now > 1262304000:
				self.backupupdate()
			else:
				print "[ImageManager] Backup Time not yet set."
				BackupTime = 0
				self.backupactivityTimer.start(36000)
		else:
			BackupTime = 0
			print "[ImageManager] Backup Schedule Disabled at", strftime("(now=%c)", localtime(now))
			self.backupactivityTimer.stop()

	def backupupdatedelay(self):
		self.backupactivityTimer.stop()
		self.backupupdate()

	def getBackupTime(self):
		backupclock = config.imagemanager.scheduletime.value
		#
		# Work out the time of the *NEXT* backup - which is the configured clock
		# time on the nth relevant day after the last recorded backup day.
		# The last backup time will have been set as 12:00 on the day it
		# happened. All we use is the actual day from that value.
		#
		lastbkup_t = int(config.imagemanager.lastbackup.value)
		if config.imagemanager.repeattype.value == "daily":
			nextbkup_t = lastbkup_t + 24*3600
		elif config.imagemanager.repeattype.value == "weekly":
			nextbkup_t = lastbkup_t + 7*24*3600
		elif config.imagemanager.repeattype.value == "monthly":
			nextbkup_t = lastbkup_t + 30*24*3600
		nextbkup = localtime(nextbkup_t)
		return int(mktime((nextbkup.tm_year, nextbkup.tm_mon, nextbkup.tm_mday, backupclock[0], backupclock[1], 0, nextbkup.tm_wday, nextbkup.tm_yday, nextbkup.tm_isdst)))

	def backupupdate(self, atLeast=0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				self.backuptimer.startLongTimer(60) # Backup missed - run it 60s from now
				print "[ImageManager] Backup Time overdue - running in 60s"
			else:
				delay = BackupTime - now # Backup in future - set the timer...
				self.backuptimer.startLongTimer(delay)
		else:
			BackupTime = -1
		print "[ImageManager] Backup Time set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
		return BackupTime

	def backupstop(self):
		self.backuptimer.stop()

	def BackuponTimer(self):
		self.backuptimer.stop()
		now = int(time())
		wake = self.getBackupTime()
		# If we're close enough, we're okay...
		atLeast = 0
		if wake - now < 60:
			print "[ImageManager] Backup onTimer occured at", strftime("%c", localtime(now))
			from Screens.Standby import inStandby

			if not inStandby and config.imagemanager.query.value:
				message = _("Your %s %s is about to create a full image backup, this can take about 6 minutes to complete.\nDo you want to allow this?") % (getMachineBrand(), getMachineName())
				ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout=30)
				ybox.setTitle('Scheduled backup.')
			else:
				print "[ImageManager] in Standby or no querying, so just running backup", strftime("%c", localtime(now))
				self.doBackup(True)
		else:
			print '[ImageManager] We are not close enough', strftime("%c", localtime(now))
			self.backupupdate(60)

	def doBackup(self, answer):
		now = int(time())
		if answer is False:
			if config.imagemanager.backupretrycount.value < 2:
				print '[ImageManager] Number of retries', config.imagemanager.backupretrycount.value
				print "[ImageManager] Backup delayed."
				repeat = config.imagemanager.backupretrycount.value
				repeat += 1
				config.imagemanager.backupretrycount.setValue(repeat)
				BackupTime = now + (int(config.imagemanager.backupretry.value) * 60)
				print "[ImageManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
				self.backuptimer.startLongTimer(int(config.imagemanager.backupretry.value) * 60)
			else:
				atLeast = 60
				print "[ImageManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout=10)
				config.imagemanager.backupretrycount.setValue(0)
				self.backupupdate(atLeast)
		else:
			print "[ImageManager] Running Backup", strftime("%c", localtime(now))
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			#      Note that fact that the job has been *scheduled*.
			#      We do *not* just note successful completion, as that would
			#      result in a loop on issues such as disk-full.
			#      Also all that we actually want to know is the day, not the time, so
			#      we actually remember midday, which avoids problems around DLST changes
			#      for backups scheduled within an hour of midnight.
			#
			sched = localtime(time())
			sched_t = int(mktime((sched.tm_year, sched.tm_mon, sched.tm_mday, 12, 0, 0, sched.tm_wday, sched.tm_yday, sched.tm_isdst)))
			config.imagemanager.lastbackup.value = sched_t
			config.imagemanager.lastbackup.save()
		#self.close()

class ImageBackup(Screen):
	skin = """
	<screen name="VIXImageManager" position="center,center" size="560,400" title="Image Manager">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session, updatebackup=False):
		Screen.__init__(self, session)
		self.Console = Console()
		self.BackupDevice = config.imagemanager.backuplocation.value
		print "[ImageManager] Device: " + self.BackupDevice
		self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
		print "[ImageManager] Directory: " + self.BackupDirectory
		self.BackupDate = strftime('%Y%m%d_%H%M%S', localtime())
		self.WORKDIR = self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-temp'
		self.TMPDIR = self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-mount'
		backupType = "-"
		if updatebackup:
			backupType = "-SoftwareUpdate-"
		imageSubBuild = ""
		if getImageType() != 'release':
			imageSubBuild = ".%s" % getImageDevBuild()
		self.MAINDESTROOT = self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + backupType + getImageVersion() + '.' + getImageBuild() + imageSubBuild + '-' + self.BackupDate
		self.MTDKERNEL = getMachineMtdKernel()
		self.KERNELFILE = getMachineKernelFile()
		self.MTDROOTFS = getMachineMtdRoot()
		self.ROOTFSFILE = getMachineRootFile()
		self.MAINDEST = self.MAINDESTROOT + '/' + getImageFolder() + '/'
		self.MODEL = getBoxType()
		self.GB4Kbin = 'boot.bin'
		self.GB4Krescue = 'rescue.bin'
		print '[ImageManager] MTD Kernel:',self.MTDKERNEL
		print '[ImageManager] MTD Root:',self.MTDROOTFS
		print '[ImageManager] Type:',getImageFileSystem()
		if 'ubi' in getImageFileSystem():
			self.ROOTDEVTYPE = 'ubifs'
			self.ROOTFSTYPE = 'ubifs'
			self.KERNELFSTYPE = 'gz'
		elif getImageFileSystem().replace(' ','') == 'tar.bz2':
			self.ROOTDEVTYPE = 'tar.bz2'
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
		elif getImageFileSystem().replace(' ','') == 'hd-emmc':
			self.ROOTDEVTYPE = 'hd-emmc'
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
		else:
			self.ROOTDEVTYPE = 'jffs2'
			self.ROOTFSTYPE= 'jffs2'
			self.KERNELFSTYPE = 'gz'
		self.swapdevice = ""
		self.RamChecked = False
		self.SwapCreated = False
		self.Stage1Completed = False
		self.Stage2Completed = False
		self.Stage3Completed = False
		self.Stage4Completed = False
		self.Stage5Completed = False

	def createBackupJob(self):
		job = Components.Task.Job(_("Image manager"))

		task = Components.Task.PythonTask(job, _("Setting up..."))
		task.work = self.JobStart
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Checking free RAM.."), timeoutCount=10)
		task.check = lambda: self.RamChecked
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating swap.."), timeoutCount=120)
		task.check = lambda: self.SwapCreated
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backing up kernel..."))
		task.work = self.doBackup1
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up kernel..."), timeoutCount=900)
		task.check = lambda: self.Stage1Completed
		task.weighting = 35

		task = Components.Task.PythonTask(job, _("Backing up root file system..."))
		task.work = self.doBackup2
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up root file system..."), timeoutCount=900)
		task.check = lambda: self.Stage2Completed
		task.weighting = 15

		task = Components.Task.PythonTask(job, _("Removing temp mounts..."))
		task.work = self.doBackup3
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Removing temp mounts..."), timeoutCount=30)
		task.check = lambda: self.Stage3Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Moving to backup Location..."))
		task.work = self.doBackup4
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Moving to backup Location..."), timeoutCount=30)
		task.check = lambda: self.Stage4Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Creating zip..."))
		task.work = self.doBackup5
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating zip..."), timeoutCount=900)
		task.check = lambda: self.Stage5Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backup complete..."))
		task.work = self.BackupComplete
		task.weighting = 5

		return job

	def JobStart(self):
		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup"):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
		except Exception, e:
			print str(e)
			print "[ImageManager] Device: " + config.imagemanager.backuplocation.value + ", i don't seem to have write access to this device."

		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail) / (1024 * 1024)
		if int(free) < 200:
			AddPopupWithCallback(self.BackupComplete,
								 _("The backup location does not have enough free space." + "\n" + self.BackupDevice + "only has " + str(free) + "MB free."),
								 MessageBox.TYPE_INFO,
								 10,
								 'RamCheckFailedNotification'
			)
		else:
			self.MemCheck()

	def MemCheck(self):
		memfree = 0
		swapfree = 0
		f = open('/proc/meminfo', 'r')
		for line in f.readlines():
			if line.find('MemFree') != -1:
				parts = line.strip().split()
				memfree = int(parts[1])
			elif line.find('SwapFree') != -1:
				parts = line.strip().split()
				swapfree = int(parts[1])
		f.close()
		TotalFree = memfree + swapfree
		print '[ImageManager] Stage1: Free Mem', TotalFree
		if int(TotalFree) < 3000:
			supported_filesystems = frozenset(('ext4', 'ext3', 'ext2'))
			candidates = []
			mounts = getProcMounts()
			for partition in harddiskmanager.getMountedPartitions(False, mounts):
				if partition.filesystem(mounts) in supported_filesystems:
					candidates.append((partition.description, partition.mountpoint))
			for swapdevice in candidates:
				self.swapdevice = swapdevice[1]
			if self.swapdevice:
				print '[ImageManager] Stage1: Creating Swapfile.'
				self.RamChecked = True
				self.MemCheck2()
			else:
				print '[ImageManager] Sorry, not enough free ram found, and no physical devices that supports SWAP attached'
				AddPopupWithCallback(self.BackupComplete,
									 _("Sorry, not enough free ram found, and no physical devices that supports SWAP attached. Can't create Swapfile on network or fat32 filesystems, unable to make backup"),
									 MessageBox.TYPE_INFO,
									 10,
									 'RamCheckFailedNotification'
				)
		else:
			print '[ImageManager] Stage1: Found Enough Ram'
			self.RamChecked = True
			self.SwapCreated = True

	def MemCheck2(self):
		self.Console.ePopen("dd if=/dev/zero of=" + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup bs=1024 count=61440", self.MemCheck3)

	def MemCheck3(self, result, retval, extra_args=None):
		if retval == 0:
			self.Console.ePopen("mkswap " + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup", self.MemCheck4)

	def MemCheck4(self, result, retval, extra_args=None):
		if retval == 0:
			self.Console.ePopen("swapon " + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup", self.MemCheck5)

	def MemCheck5(self, result, retval, extra_args=None):
		self.SwapCreated = True

	def doBackup1(self):
		print '[ImageManager] Stage1: Creating tmp folders.', self.BackupDirectory
		print '[ImageManager] Stage1: Creating backup Folders.'
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		mkdir(self.WORKDIR, 0644)
		if path.exists(self.TMPDIR + '/root') and path.ismount(self.TMPDIR + '/root'):
			system('umount ' + self.TMPDIR + '/root')
		elif path.exists(self.TMPDIR + '/root'):
			rmtree(self.TMPDIR + '/root')
		if path.exists(self.TMPDIR):
			rmtree(self.TMPDIR)
		makedirs(self.TMPDIR, 0644)
		if self.ROOTDEVTYPE != 'hd-emmc':
			makedirs(self.TMPDIR + '/root', 0644)
		makedirs(self.MAINDESTROOT, 0644)
		self.commands = []
		makedirs(self.MAINDEST, 0644)
		if self.ROOTDEVTYPE != 'hd-emmc':
			print '[ImageManager] Stage1: Making Kernel Image.'
			if self.KERNELFSTYPE == 'bin':
				self.command = 'dd if=/dev/%s of=%s/vmlinux.bin' % (self.MTDKERNEL ,self.WORKDIR)
			else:
				self.command = 'nanddump /dev/%s -f %s/vmlinux.gz' % (self.MTDKERNEL ,self.WORKDIR)
			self.Console.ePopen(self.command, self.Stage1Complete)
		else:
			print "[ImageManager] Stage1: Skipping make Kernel Image, as we don't need it"
			self.Stage1Complete('pass', 0)

	def Stage1Complete(self, result, retval, extra_args=None):
		if retval == 0:
			self.Stage1Completed = True
			print '[ImageManager] Stage1: Complete.'

	def doBackup2(self):
		print '[ImageManager] Stage2: Making Root Image.'
		if self.ROOTDEVTYPE == 'jffs2':
			print '[ImageManager] Stage2: JFFS2 Detected.'
			if getMachineBuild() == 'gb800solo':
				JFFS2OPTIONS = " --disable-compressor=lzo -e131072 -l -p125829120"
			else:
				JFFS2OPTIONS = " --disable-compressor=lzo --eraseblock=0x20000 -n -l"
			self.commands.append('mount --bind / %s/root' % self.TMPDIR)
			self.commands.append('mkfs.jffs2 --root=%s/root --faketime --output=%s/rootfs.jffs2 %s' % (self.TMPDIR, self.WORKDIR, JFFS2OPTIONS))
		elif self.ROOTDEVTYPE == 'tar.bz2':
			print '[ImageManager] Stage2: TAR.BZIP Detected.'
			self.commands.append('mount --bind / %s/root' % self.TMPDIR)
			self.commands.append("/bin/tar -cf %s/rootfs.tar -C %s/root --exclude=/var/nmbd/* ." % (self.WORKDIR, self.TMPDIR))
			self.commands.append("/usr/bin/bzip2 %s/rootfs.tar" % self.WORKDIR)
		elif self.MODEL in ("gbquad4k","gbue4k"):
			self.commands.append("dd if=/dev/mmcblk0p1 of=%s/boot.bin" % self.WORKDIR)
			self.commands.append("dd if=/dev/mmcblk0p3 of=%s/rescue.bin" % self.WORKDIR)
			print '[ImageManager] Stage2: Create: boot dump boot.bin:',self.MODEL
			print '[ImageManager] Stage2: Create: rescue dump rescue.bin:',self.MODEL
		elif self.ROOTDEVTYPE == 'hd-emmc':
			print '[ImageManager] Stage2: EMMC Detected.'
			self.MTDBOOT_HD51 = "mmcblk0p1"
			self.EMMCIMG = "disk.img"
			BLOCK_SIZE=512
			BLOCK_SECTOR=2
			IMAGE_ROOTFS_ALIGNMENT=1024
			BOOT_PARTITION_SIZE=3072
			KERNEL_PARTITION_OFFSET = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			KERNEL_PARTITION_SIZE=8192
			ROOTFS_PARTITION_OFFSET = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			ROOTFS_PARTITION_SIZE=819200
			SECOND_KERNEL_PARTITION_OFFSET = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			SECOND_ROOTFS_PARTITION_OFFSET = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			THIRD_KERNEL_PARTITION_OFFSET = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			THIRD_ROOTFS_PARTITION_OFFSET = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			FOURTH_KERNEL_PARTITION_OFFSET = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			FOURTH_ROOTFS_PARTITION_OFFSET = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SWAP_PARTITION_OFFSET = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			EMMC_IMAGE = "%s/%s"% (self.WORKDIR,self.EMMCIMG)
			EMMC_IMAGE_SIZE=3817472
			EMMC_IMAGE_SEEK = int(EMMC_IMAGE_SIZE) * int(BLOCK_SECTOR)
			self.commands.append('dd if=/dev/zero of=%s bs=%s count=0 seek=%s' % (EMMC_IMAGE, BLOCK_SIZE , EMMC_IMAGE_SEEK))
			self.commands.append('parted -s %s mklabel gpt' %EMMC_IMAGE)
			PARTED_END_BOOT = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart boot fat16 %s %s' % (EMMC_IMAGE, IMAGE_ROOTFS_ALIGNMENT, PARTED_END_BOOT ))
			PARTED_END_KERNEL1 = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart kernel1 %s %s' % (EMMC_IMAGE, KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL1 ))
			PARTED_END_ROOTFS1 = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart rootfs1 ext4 %s %s' % (EMMC_IMAGE, ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS1 ))
			PARTED_END_KERNEL2 = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart kernel2 %s %s' % (EMMC_IMAGE, SECOND_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL2 ))
			PARTED_END_ROOTFS2 = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart rootfs2 ext4 %s %s' % (EMMC_IMAGE, SECOND_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS2 ))
			PARTED_END_KERNEL3 = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart kernel3 %s %s' % (EMMC_IMAGE, THIRD_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL3 ))
			PARTED_END_ROOTFS3 = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart rootfs3 ext4 %s %s' % (EMMC_IMAGE, THIRD_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS3 ))
			PARTED_END_KERNEL4 = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart kernel4 %s %s' % (EMMC_IMAGE, FOURTH_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL4 ))
			PARTED_END_ROOTFS4 = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commands.append('parted -s %s unit KiB mkpart rootfs4 ext4 %s %s' % (EMMC_IMAGE, FOURTH_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS4 ))
			self.commands.append('parted -s %s unit KiB mkpart swap linux-swap %s 100%%' % (EMMC_IMAGE, SWAP_PARTITION_OFFSET))
			BOOT_IMAGE_SEEK = int(IMAGE_ROOTFS_ALIGNMENT) * int(BLOCK_SECTOR)
			self.commands.append('dd if=/dev/%s of=%s seek=%s' % (self.MTDBOOT_HD51, EMMC_IMAGE, BOOT_IMAGE_SEEK ))
			KERNEL_IMAGE_SEEK = int(KERNEL_PARTITION_OFFSET) * int(BLOCK_SECTOR)
			self.commands.append('dd if=/dev/%s of=%s seek=%s' % (self.MTDKERNEL, EMMC_IMAGE, KERNEL_IMAGE_SEEK ))
			ROOTFS_IMAGE_SEEK = int(ROOTFS_PARTITION_OFFSET) * int(BLOCK_SECTOR)
			self.commands.append('dd if=/dev/%s of=%s seek=%s' % (self.MTDROOTFS, EMMC_IMAGE, ROOTFS_IMAGE_SEEK ))
		else:
			print '[ImageManager] Stage2: UBIFS Detected.'
			UBINIZE_ARGS = getMachineUBINIZE()
			MKUBIFS_ARGS = getMachineMKUBIFS()
			output = open('%s/ubinize.cfg' % self.WORKDIR, 'w')
			output.write('[ubifs]\n')
			output.write('mode=ubi\n')
			output.write('image=%s/root.ubi\n' % self.WORKDIR)
			output.write('vol_id=0\n')
			output.write('vol_type=dynamic\n')
			output.write('vol_name=rootfs\n')
			output.write('vol_flags=autoresize\n')
			output.close()
			self.commands.append('mount --bind / %s/root' % self.TMPDIR)
			self.commands.append('touch %s/root.ubi' % self.WORKDIR)
			self.commands.append('mkfs.ubifs -r %s/root -o %s/root.ubi %s' % (self.TMPDIR, self.WORKDIR, MKUBIFS_ARGS))
			self.commands.append('ubinize -o %s/rootfs.ubifs %s %s/ubinize.cfg' % (self.WORKDIR, UBINIZE_ARGS, self.WORKDIR))
		self.Console.eBatch(self.commands, self.Stage2Complete, debug=False)

	def Stage2Complete(self, extra_args=None):
		if len(self.Console.appContainers) == 0:
			self.Stage2Completed = True
			print '[ImageManager] Stage2: Complete.'

	def doBackup3(self):
		print '[ImageManager] Stage3: Unmounting and removing tmp system'
		if path.exists(self.TMPDIR + '/root') and path.ismount(self.TMPDIR + '/root'):
			self.command = 'umount ' + self.TMPDIR + '/root && rm -rf ' + self.TMPDIR
			self.Console.ePopen(self.command, self.Stage3Complete)
		else:
			if path.exists(self.TMPDIR):
				rmtree(self.TMPDIR)
			self.Stage3Complete('pass', 0)

	def Stage3Complete(self, result, retval, extra_args=None):
		if retval == 0:
			self.Stage3Completed = True
			print '[ImageManager] Stage3: Complete.'

	def doBackup4(self):
		print '[ImageManager] Stage4: Moving from work to backup folders'
		if self.ROOTDEVTYPE == 'hd-emmc' and path.exists('%s/disk.img' % self.WORKDIR):
			move('%s/disk.img' % self.WORKDIR, '%s/disk.img' % self.MAINDEST)
		else:
			move('%s/rootfs.%s' % (self.WORKDIR, self.ROOTFSTYPE), '%s/%s' % (self.MAINDEST, self.ROOTFSFILE))
			if self.KERNELFSTYPE == 'bin' and path.exists('%s/vmlinux.bin' % self.WORKDIR):
				move('%s/vmlinux.bin' % self.WORKDIR, '%s/%s' % (self.MAINDEST, self.KERNELFILE))
			else:
				move('%s/vmlinux.gz' % self.WORKDIR, '%s/%s' % (self.MAINDEST, self.KERNELFILE))
		if self.MODEL in ("gbquad4k","gbue4k"):
			move('%s/%s' % (self.WORKDIR, self.GB4Kbin), '%s/%s' % (self.MAINDEST, self.GB4Kbin))
			move('%s/%s' % (self.WORKDIR, self.GB4Krescue), '%s/%s' % (self.MAINDEST, self.GB4Krescue))
			system('cp -f /usr/share/gpt.bin %s/gpt.bin' %(self.MAINDEST))
		fileout = open(self.MAINDEST + '/imageversion', 'w')
		line = defaultprefix + '-' + getImageType() + '-backup-' + getImageVersion() + '.' + getImageBuild() + '-' + self.BackupDate
		fileout.write(line)
		fileout.close()
		if getBrandOEM() ==  'vuplus':
			if getMachineBuild() == 'vuzero':
				fileout = open(self.MAINDEST + '/force.update', 'w')
				line = "This file forces the update."
				fileout.write(line)
				fileout.close()
			else:
				fileout = open(self.MAINDEST + '/reboot.update', 'w')
				line = "This file forces a reboot after the update."
				fileout.write(line)
				fileout.close()
			imagecreated = True
		elif getBrandOEM() in ('xtrend', 'gigablue', 'octagon', 'odin', 'xp', 'ini'):
			if getBrandOEM() in ('xtrend', 'octagon', 'odin', 'ini'):
				fileout = open(self.MAINDEST + '/noforce', 'w')
				line = "rename this file to 'force' to force an update without confirmation"
				fileout.write(line)
				fileout.close()
			if path.exists('/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat'):
				copy('/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat', self.MAINDESTROOT + '/burn.bat')
		print '[ImageManager] Stage4: Removing Swap.'
		if path.exists(self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup"):
			system('swapoff ' + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
			remove(self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		if (path.exists(self.MAINDEST + '/' + self.ROOTFSFILE) and path.exists(self.MAINDEST + '/' + self.KERNELFILE)) or (self.ROOTDEVTYPE == 'hd-emmc' and path.exists('%s/disk.img' % self.MAINDEST)):
			for root, dirs, files in walk(self.MAINDEST):
				for momo in dirs:
					chmod(path.join(root, momo), 0644)
				for momo in files:
					chmod(path.join(root, momo), 0644)
			print '[ImageManager] Stage4: Image created in ' + self.MAINDESTROOT
			self.Stage4Complete()
		else:
			print "[ImageManager] Stage4: Image creation failed - e. g. wrong backup destination or no space left on backup device"
			self.BackupComplete()

	def Stage4Complete(self):
		self.Stage4Completed = True
		print '[ImageManager] Stage4: Complete.'

	def doBackup5(self):
		zipfolder = path.split(self.MAINDESTROOT)
		self.commands = []
		self.commands.append('cd ' + self.MAINDESTROOT + ' && zip -r ' + self.MAINDESTROOT + '.zip *')
		self.commands.append('rm -rf ' + self.MAINDESTROOT)
		self.Console.eBatch(self.commands, self.Stage5Complete, debug=True)

	def Stage5Complete(self, anwser=None):
		self.Stage5Completed = True
		print '[ImageManager] Stage5: Complete.'

	def BackupComplete(self, anwser=None):
		#    trim the number of backups kept...
		#    [Also NOTE that this and the preceding def define an unused arg
		#     with what looks like a typo - that should surely be "answer"]
		#
		import fnmatch
		try:
			if config.imagemanager.number_to_keep.value > 0 \
			 and path.exists(self.BackupDirectory): # !?!
				images = listdir(self.BackupDirectory)
				patt = config.imagemanager.folderprefix.value + '-*.zip'
				emlist = []
				for fil in images:
					if fnmatch.fnmatchcase(fil, patt):
						emlist.append(fil)
				# sort by oldest first...
				emlist.sort(key=lambda fil: path.getmtime(self.BackupDirectory + fil))
				# ...then, if we have too many, remove the <n> newest from the end
				# and delete what is left
				if len(emlist) > config.imagemanager.number_to_keep.value:
					emlist = emlist[0:len(emlist)-config.imagemanager.number_to_keep.value]
					for fil in emlist:
						remove(self.BackupDirectory + fil)
		except:
			pass
		if config.imagemanager.schedule.value:
			atLeast = 60
			autoImageManagerTimer.backupupdate(atLeast)
		else:
			autoImageManagerTimer.backupstop()

class ImageManagerDownload(Screen):
	skin = """
	<screen name="VIXImageManager" position="center,center" size="560,400" title="Image Manager" flags="wfBorder" >
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" />
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand" />
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session, menu_path, BackupDirectory):
		Screen.__init__(self, session)
		screentitle = _("Downloads")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self.BackupDirectory = BackupDirectory
		self['lab1'] = Label(_("Select an image to Download:"))
		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("Download"))

		self.onChangedEntry = []
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()

		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def selectionChanged(self):
		for x in self.onChangedEntry:
			x()

	def populate_List(self):
		try:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
										  {
										  'cancel': self.close,
										  'red': self.close,
										  'green': self.keyDownload,
										  'ok': self.keyDownload,
										  }, -1)

			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)

			import urllib2
			from bs4 import BeautifulSoup

			supportedMachines = {
				'axodinc'         : 'Opticum-AX-ODIN-DVBC-1',
				'et10000'         : 'ET-10x00',
				'et4x00'          : 'ET-4x00',
				'et5x00'          : 'ET-5x00',
				'et6x00'          : 'ET-6x00',
				'et7x00'          : 'ET-7x00',
				'et8000'          : 'ET-8000',
				'et8500'          : 'ET-8500',
				'et9x00'          : 'ET-9x00',
				'formuler4turbo'  : 'Formuler4turbo',
				'gb800se'         : 'GiGaBlue-HD800SE',
				'gb800seplus'     : 'GiGaBlue-HD800SE-PLUS',
				'gb800ue'         : 'GiGaBlue-HD800UE',
				'gb800ueplus'     : 'GiGaBlue-HD800UE-PLUS',
				'gbquad'          : 'GiGaBlue-HD-QUAD',
				'gbquadplus'      : 'GiGaBlue-HD-QUAD-PLUS',
				'gbquad4k'        : 'GiGaBlue-HD-QUAD-4K',
				'gbultraue'       : 'GiGaBlue-HD-ULTRA-UE',
				'gbx1'            : 'GiGaBlue-HD-X1',
				'gbx3'            : 'GiGaBlue-HD-X3',
				'iqonios100hd'    : 'iqon-IOS-100HD',
				'iqonios200hd'    : 'iqon-IOS-200HD',
				'iqonios300hd'    : 'iqon-IOS-300HD',
				'ixusszero'       : 'Medialink-IXUSS-ZERO',
				'maram9'          : 'Mara-M9',
				'mbhybrid'        : 'Miraclebox-Mini-Hybrid',
				'mbmicro'         : 'Miraclebox-Micro',
				'mbmicrov2'       : 'Miraclebox-Microv2',
				'mbmini'          : 'Miraclebox-Mini',
				'mbminiplus'      : 'Miraclebox-MiniPlus',
				'mbtwin'          : 'Miraclebox-Twin',
				'mbtwinplus'      : 'Miraclebox-Twinplus',
				'mbultra'         : 'Miraclebox-Ultra',
				'mutant11'        : 'Mutant-HD11',
				'mutant1200'      : 'Mutant-HD1200',
				'mutant1500'      : 'Mutant-HD1500',
				'mutant2400'      : 'Mutant-HD2400',
				'mutant500c'      : 'Mutant-HD500C',
				'mutant51'        : 'Mutant-HD51',
				'osmega'          : 'OS-mega',
				'osmini'          : 'OS-mini',
				'osminiplus'      : 'OS-miniplus',
				'qb800solo'       : 'GiGaBlue-HD800Solo',
				'sf8'             : 'OCTAGON-SF8-HD',
				'sf128'           : 'OCTAGON-SF128',
				'sf138'           : 'OCTAGON-SF138',
				'sf228'           : 'OCTAGON-SF228',
				'sf4008'          : 'OCTAGON-SF4008',
				'spycat'          : 'Spycat',
				'tm2t'            : 'TM-2T',
				'tmnano'          : 'TM-Nano-OE',
				'tmnano2super'    : 'TM-Nano2-Super',
				'tmnano2t'        : 'TM-Nano-2T',
				'tmnano3t'        : 'TM-Nano-3T',
				'tmnanose'        : 'TM-Nano-SE',
				'tmnanosecombo'   : 'TM-Nano-SE-Combo',
				'tmnanosem2'      : 'TM-Nano-SE-M2',
				'tmnanosem2plus'  : 'TM-Nano-SE-M2-Plus',
				'tmnanom3'        : 'TM-Nano-M3',
				'tmnanoseplus'    : 'TM-Nano-SE-Plus',
				'tmsingle'        : 'TM-Single',
				'tmtwin'          : 'TM-Twin-OE',
				'tmtwin4k'        : 'TM-Twin-4K',
				'uniboxhde'       : 'Venton-Unibox-HDeco-PLUS',
				'ventonhdx'       : 'Venton-Unibox-HDx',
				'vuduo'           : 'Vu+Duo',
				'vuduo2'          : 'Vu+Duo2',
				'vusolo'          : 'Vu+Solo',
				'vusolo2'         : 'Vu+Solo2',
				'vusolo4k'        : 'Vu+Solo4K',
				'vusolose'        : 'Vu+Solo-SE',
				'vuultimo'        : 'Vu+Ultimo',
				'vuultimo4k'      : 'Vu+Ultimo4K',
				'vuuno'           : 'Vu+Uno',
				'vuuno4k'         : 'Vu+Uno4K',
				'vuzero'          : 'Vu+Zero',
				'xp1000max'       : 'MaxDigital-XP1000',
				'xp1000plus'      : 'OCTAGON-XP1000PLUS',
				'xpeedlx'         : 'GI-Xpeed-LX',
				'xpeedlx3'        : 'GI-Xpeed-LX3'
			}

# Ensure this item is missing before we check box support...
			try:
				del self._error_message
			except:
				pass
			try:
				self.boxtype = supportedMachines[getMachineMake()]
			except:
				print "[ImageManager][populate_List] the %s is not currently supported by OpenViX." % getMachineMake()
				self._error_message =  _("The %s is not currently supported by OpenViX.") % getMachineMake()
				self["key_green"].setText(_("Show Error"))
				self["key_green"].show()
				self.emlist.append(_("**ERROR**"))
				self["list"].setList(self.emlist)
				self["list"].show()
				return

			url = 'http://www.openvix.co.uk/openvix-builds/'+self.boxtype+'/'
			conn = urllib2.urlopen(url)
			html = conn.read()

			soup = BeautifulSoup(html)
			links = soup.find_all('a')

			del self.emlist[:]
			for tag in links:
				link = tag.get('href',None)
				if link != None and link.endswith('zip') and link.find(getMachineMake()) != -1:
					self.emlist.append(str(link))

			self.emlist.sort()
			self.emlist.reverse()
		except:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
										  {
										  'cancel': self.close,
										  'red': self.close,
										  }, -1)
			self.emlist.append(" ")
			self["list"].setList(self.emlist)
			self["list"].show()

	def keyDownload(self):
		if hasattr(self, "_error_message"):
			self.session.open(MessageBox, self._error_message, MessageBox.TYPE_INFO, timeout=10)
			return
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to download this image:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDownload, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Download confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to download."), MessageBox.TYPE_INFO, timeout=10)

	def doDownload(self, answer):
		if answer is True:
			selectedimage = self['list'].getCurrent()
			fileurl = 'http://www.openvix.co.uk/openvix-builds/%s/%s' % (self.boxtype, selectedimage)
			fileloc = self.BackupDirectory + selectedimage
			Tools.CopyFiles.downloadFile(fileurl, fileloc, selectedimage.replace('_usb',''))
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Downloading")):
					break
			self.showJobView(job)

	def showJobView(self, job):
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, backgroundable=True, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def myclose(self, result, retval, extra_args):
		remove(self.BackupDirectory + self.selectedimage)
		self.close()
