import Components.Task
from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Pixmap import MultiPixmap, Pixmap
from Components.config import configfile , config, ConfigYesNo, ConfigSubsection, getConfigListEntry, ConfigSelection, ConfigText, ConfigClock, ConfigNumber, NoSave
from Components.ConfigList import ConfigListScreen
from Components.Harddisk import harddiskmanager
from Components.Language import language
from Screens.Screen import Screen
from Components.Console import Console
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Tools.Directories import pathExists, fileExists, resolveFilename,SCOPE_LANGUAGE, SCOPE_PLUGINS, SCOPE_CURRENT_PLUGIN, SCOPE_CURRENT_SKIN, SCOPE_METADIR
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer, quitMainloop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, eListboxPythonMultiContent, eListbox, gFont, getDesktop, ePicLoad
from ServiceReference import ServiceReference
from os import path, system, unlink, stat, mkdir, popen, makedirs, chdir, getcwd, listdir, rename, remove, access, W_OK, R_OK, F_OK, environ, statvfs
import datetime, gettext
from shutil import rmtree, move, copy
from time import localtime, time, strftime, mktime, sleep
from enigma import eTimer

lang = language.getLanguage()
environ["LANGUAGE"] = lang[:2]
print "[ImageManager] set language to ", lang[:2]
gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
gettext.textdomain("enigma2")
gettext.bindtextdomain("ImageManager", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "SystemPlugins/ViX/locale"))

def _(txt):
	t = gettext.dgettext("ImageManager", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t

autoImageManagerTimer = None

def ImageManagerautostart(reason, session=None, **kwargs):
	"called with reason=1 to during /sbin/shutdown.sysvinit, with reason=0 at startup?"
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
		print "[ImageManager] Stop"
		autoImageManagerTimer.stop()        

class VIXImageManager(Screen):
	skin = """<screen name="VIXImageManager" position="center,center" size="560,400" title="Image Manager" flags="wfBorder" >
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
		<widget name="backupstatus" position="10,370" size="400,30" font="Regular;20" zPosition="5" />
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""


	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Image Manager"))

		self['lab1'] = Label()
		self["backupstatus"] = Label()
		self["key_red"] = Button(_("Refresh List"))
		self["key_green"] = Button()
		self["key_yellow"] = Button(_("Restore"))
		self["key_blue"] = Button(_("Delete"))

		self.BackupRunning = False
		self.onChangedEntry = [ ]
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.backupRunning)
		self.activityTimer.start(10)

		if BackupTime > 0:
			backuptext = _("Next Backup: ") + strftime("%c", localtime(BackupTime))
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def backupRunning(self):
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			jobname = str(job.name)
			if jobname.startswith('ImageManager'):
				self.BackupRunning = True
		if self.BackupRunning:
			self["key_green"].setText(_("View Progress"))
		else:
			self["key_green"].setText(_("New Backup"))
		self.activityTimer.startLongTimer(5)

	def refreshUp(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if not fil.endswith('swapfile_backup') and not fil.endswith('bi'):
				self.emlist.append(fil)
		self.emlist.sort()
		self["list"].setList(self.emlist)
		self["list"].show()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveUp)

	def refreshDown(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if not fil.endswith('swapfile_backup') and not fil.endswith('bi'):
				self.emlist.append(fil)
		self.emlist.sort()
		self["list"].setList(self.emlist)
		self["list"].show()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveDown)

	def selectionChanged(self):
		for x in self.onChangedEntry:
			x()
		
	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))

	def showJobView(self, job):
		from Screens.TaskView import JobView
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job)
	
	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def populate_List(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if pathExists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.imagemanager.backuplocation.setChoices(imparts)

		if config.imagemanager.backuplocation.value.startswith('/media/net/'):
			mount1 = config.imagemanager.backuplocation.value.replace('/','')
			mount1 = mount1.replace('medianet','/media/net/')
			mount = config.imagemanager.backuplocation.value, mount1
		else:
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value
		hdd = '/media/hdd/','/media/hdd/'
		if mount not in config.imagemanager.backuplocation.choices.choices:
			if hdd in config.imagemanager.backuplocation.choices.choices:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
					{
						'cancel': self.close,
						'red': self.populate_List,
						'green': self.GreenPressed,
						'yellow': self.keyResstore,
						'blue': self.keyDelete,
						"menu": self.createSetup,
						"up": self.refreshUp,
						"down": self.refreshDown,
					}, -1)

				self.BackupDirectory = '/media/hdd/imagebackups/'
				config.imagemanager.backuplocation.value = '/media/hdd/'
				config.imagemanager.backuplocation.save
				self['lab1'].setText(_("The chosen location does not exist, using /media/hdd") + _("\nSelect an image to Restore / Delete:"))
			else:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
					{
						'cancel': self.close,
						"menu": self.createSetup,
					}, -1)

				self['lab1'].setText(_("Device: None available") + _("\nSelect an image to Restore / Delete:"))
		else:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
				{
					'cancel': self.close,
					'red': self.populate_List,
					'green': self.GreenPressed,
					'yellow': self.keyResstore,
					'blue': self.keyDelete,
					"menu": self.createSetup,
					"up": self.refreshUp,
					"down": self.refreshDown,
				}, -1)

			self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + _("\nSelect an image to Restore / Delete:"))

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
			images = listdir(self.BackupDirectory)
			del self.emlist[:]
			for fil in images:
				if not fil.endswith('swapfile_backup') and not fil.endswith('bi'):
					self.emlist.append(fil)
			self.emlist.sort()
			self["list"].setList(self.emlist)
			self["list"].show()
		except:
			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + _("\nthere was a problem with this device, please reformat and try again."))

	def createSetup(self):
		self.session.openWithCallback(self.setupDone, ImageManagerMenu)

	def setupDone(self):
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
			backuptext = _("Next Backup: ") + strftime("%c", localtime(BackupTime))
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))

	def keyDelete(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to delete this backup:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDelete, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Remove Confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to delete."), MessageBox.TYPE_INFO, timeout = 10)

	def doDelete(self, answer):
		if answer is True:
			self.sel = self['list'].getCurrent()
			self["list"].instance.moveSelectionTo(0)
			rmtree(self.BackupDirectory + self.sel)
		self.populate_List()

	def GreenPressed(self):
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			jobname = str(job.name)
			if jobname.startswith('ImageManager'):
				self.BackupRunning = True
		if self.BackupRunning:
			self.showJobView(job)
		else:
			self.keyBackup()

	def keyBackup(self):
		if config.misc.boxtype.value == "vuuno" or config.misc.boxtype.value == "vuultimo" or config.misc.boxtype.value == "vusolo" or config.misc.boxtype.value == "vuduo" or config.misc.boxtype.value == "et9000" or config.misc.boxtype.value == "et5000":
			message = _("Are you ready to create a backup image ?")
			ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Backup Confirmation"))
		else:
			self.session.open(MessageBox, _("Sorry you box is not yet compatible."), MessageBox.TYPE_INFO, timeout = 10)
 
	def doBackup(self,answer):
		if answer is True:
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			self.BackupRunning = True
			self["key_green"].setText(_("View Progress"))
			self["key_green"].show()

	def keyResstore(self):
		self.sel = self['list'].getCurrent()
		if not self.BackupRunning:
			if not config.crash.enabledebug.value:
				if (config.misc.boxtype.value == "vuuno" and path.exists(self.BackupDirectory + self.sel + '/vuplus/uno')) or (config.misc.boxtype.value == "vuultimo" and path.exists(self.BackupDirectory + self.sel + '/vuplus/ultimo')) or (config.misc.boxtype.value == "vusolo" and path.exists(self.BackupDirectory + self.sel + '/vuplus/solo')) or (config.misc.boxtype.value == "vuduo" and path.exists(self.BackupDirectory + self.sel + '/vuplus/duo')) or (config.misc.boxtype.value == "et9000" and path.exists(self.BackupDirectory + self.sel + '/et9000')) or (config.misc.boxtype.value == "et5000" and path.exists(self.BackupDirectory + self.sel + '/et5000')):
					if self.sel:
						message = _("Are you sure you want to restore this image:\n ") + self.sel
						ybox = self.session.openWithCallback(self.RestoreMemCheck, MessageBox, message, MessageBox.TYPE_YESNO)
						ybox.setTitle(_("Restore Confirmation"))
					else:
						self.session.open(MessageBox, _("You have no image to restore."), MessageBox.TYPE_INFO, timeout = 10)
				else:
					self.session.open(MessageBox, _("Sorry the image " + self.sel + " is not compatible with this box."), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Sorry you have Debug Logs enabed,\nPlease disable and restart GUI, before trying again"), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.session.open(MessageBox, _("Backup in progress,\nPlease for it to finish, before trying again"), MessageBox.TYPE_INFO, timeout = 10)

	def RestoreMemCheck(self,answer):
		if answer is True:
			try:
				memcheck_stdout = popen('free | grep Total | tr -s " " | cut -d " " -f 4', "r")
				memcheck = memcheck_stdout.read()
				if int(memcheck) < 3000:
					if not config.imagemanager.backuplocation.value.startswith('/media/net/'):
						mycmd1 = "echo '************************************************************************'"
						mycmd2 = "echo 'Creating swapfile'"
						mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup bs=1024 count=61440"
						mycmd4 = "mkswap " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"
						mycmd5 = "swapon " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"
						mycmd6 = "echo '************************************************************************'"
						self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doResstore,closeOnSuccess = True)
					else:
						self.doResstore()
			except:
				mycmd1 = "echo '************************************************************************'"
				mycmd2 = "echo 'Creating swapfile'"
				mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup bs=1024 count=61440"
				mycmd4 = "mkswap " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"
				mycmd5 = "swapon " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"
				mycmd6 = "echo '************************************************************************'"
				self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doResstore,closeOnSuccess = True)

	def doResstore(self):
		NANDWRITE='/usr/bin/nandwrite'
		selectedimage = self.sel
		if config.misc.boxtype.value == "vusolo" or config.misc.boxtype.value == "vuduo":
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + config.misc.boxtype.value +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "echo ' '"
			mycmd5 = "echo 'Attention:'"
			mycmd6 = "echo ' '"
			mycmd7 = "echo 'Your Vuplus will be rebooted automatically after the flashing progress.'"
			mycmd8 = "echo ' '"
			mycmd9 = "echo 'Preparing Flashprogress.'"
			mycmd10 = "echo 'Erasing Boot aera.'"
			mycmd11 = 'flash_eraseall -j -q /dev/mtd2'
			mycmd12 = "echo 'Flasing Boot to NAND.'"
			mycmd13 = NANDWRITE + ' -p -q /dev/mtd2 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/boot_cfe_auto.jffs2'
			mycmd14 = "echo 'Erasing Root aera.'"
			mycmd15 = 'flash_eraseall -j -q /dev/mtd0'
			mycmd16 = "echo 'Flasing Root to NAND.'"
			mycmd17 = NANDWRITE + ' -p -q /dev/mtd0 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/root_cfe_auto.jffs2'
			mycmd18 = "echo 'Erasing Kernel aera.'"
			mycmd19 = 'flash_eraseall -j -q /dev/mtd1'
			mycmd20 = "echo 'Flasing Kernel to NAND.'"
			mycmd21 = NANDWRITE + ' -p -q /dev/mtd1 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/kernel_cfe_auto.bin'
			mycmd22 = "echo ' '"
			mycmd23 = "echo 'Flasing Complete\nRebooting.'"
			mycmd24 = "sleep 2"
			mycmd25 = "/sbin/shutdown.sysvinit -r now"
			self.session.open(Console, title='Flashing NAND...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22, mycmd23, mycmd24, mycmd25],closeOnSuccess = True)
		elif config.misc.boxtype.value == "vuuno" or config.misc.boxtype.value == "vuultimo":
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + config.misc.boxtype.value +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "echo ' '"
			mycmd5 = "echo 'Attention:'"
			mycmd6 = "echo ' '"
			mycmd7 = "echo 'Your Vuplus will be rebooted automatically after the flashing progress.'"
			mycmd8 = "echo ' '"
			mycmd9 = "echo 'Preparing Flashprogress.'"
			mycmd10 = "echo 'Erasing Bootsplash aera.'"
			mycmd11 = 'flash_eraseall -j -q /dev/mtd3'
			mycmd12 = "echo 'Flasing Bootsplash to NAND.'"
			mycmd13 = NANDWRITE + ' -p -q /dev/mtd3 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/splash_cfe_auto.bin'
			mycmd14 = "echo 'Erasing Boot aera.'"
			mycmd15 = 'flash_eraseall -j -q /dev/mtd2'
			mycmd16 = "echo 'Flasing Boot to NAND.'"
			mycmd17 = NANDWRITE + ' -p -q /dev/mtd2 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/boot_cfe_auto.jffs2'
			mycmd18 = "echo 'Erasing Root aera.'"
			mycmd19 = 'flash_eraseall -j -q /dev/mtd0'
			mycmd20 = "echo 'Flasing Root to NAND.'"
			mycmd21 = NANDWRITE + ' -p -q /dev/mtd0 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/root_cfe_auto.jffs2'
			mycmd22 = "echo 'Erasing Kernel aera.'"
			mycmd23 = 'flash_eraseall -j -q /dev/mtd1'
			mycmd24 = "echo 'Flasing Kernel to NAND.'"
			mycmd25 = NANDWRITE + ' -p -q /dev/mtd1 ' + self.BackupDirectory + selectedimage + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/kernel_cfe_auto.bin'
			mycmd26 = "echo ' '"
			mycmd27 = "echo 'Flasing Complete\nRebooting.'"
			mycmd28 = "sleep 2"
			mycmd29 = "/sbin/shutdown.sysvinit -r now"
			self.session.open(Console, title='Flashing NAND...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22, mycmd23, mycmd24, mycmd25, mycmd26, mycmd27, mycmd28, mycmd29],closeOnSuccess = True)
		elif config.misc.boxtype.value == "et9000" or config.misc.boxtype.value == "et5000":
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Xtrend " + config.misc.boxtype.value +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "echo ' '"
			mycmd5 = "echo 'Attention:'"
			mycmd6 = "echo ' '"
			mycmd7 = "echo 'Your Xtrend will be rebooted automatically after the flashing progress.'"
			mycmd8 = "echo ' '"
			mycmd9 = "echo 'Preparing Flashprogress.'"
			mycmd10 = "echo 'Erasing Boot aera.'"
			mycmd11 = 'flash_eraseall -j -q /dev/mtd2'
			mycmd12 = "echo 'Flasing Boot to NAND.'"
			mycmd13 = NANDWRITE + ' -p -q /dev/mtd2 ' + self.BackupDirectory + selectedimage + '/' + config.misc.boxtype.value + '/boot.bin'
			mycmd14 = "echo 'Erasing Root aera.'"
			mycmd15 = 'flash_eraseall -j -q /dev/mtd3'
			mycmd16 = "echo 'Flasing Root to NAND.'"
			mycmd17 = NANDWRITE + ' -p -q /dev/mtd3 ' + self.BackupDirectory + selectedimage + '/' + config.misc.boxtype.value + '/rootfs.bin'
			mycmd18 = "echo 'Erasing Kernel aera.'"
			mycmd19 = 'flash_eraseall -j -q /dev/mtd1'
			mycmd20 = "echo 'Flasing Kernel to NAND.'"
			mycmd21 = NANDWRITE + ' -p -q /dev/mtd1 ' + self.BackupDirectory + selectedimage + '/' + config.misc.boxtype.value + '/kernel.bin'
			mycmd22 = "echo ' '"
			mycmd23 = "echo 'Flasing Complete\nRebooting.'"
			mycmd24 = "sleep 2"
			mycmd25 = "/sbin/shutdown.sysvinit -r now"
			self.session.open(Console, title='Flashing NAND...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22, mycmd23, mycmd24, mycmd25],closeOnSuccess = True)

	def myclose(self):
		self.close()

class ImageManagerMenu(ConfigListScreen, Screen):
	sz_w = getDesktop(0).size().width()
	if sz_w == 1280:
		skin = """
			<screen name="ImageManagerMenu" position="center,center" size="500,285" title="Image Manager Setup">
				<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
				<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
				<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
				<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
				<widget name="config" position="10,45" size="480,150" scrollbarMode="showOnDemand" />
				<widget name="HelpWindow" pixmap="skin_default/vkey_icon.png" position="445,400" zPosition="1" size="500,285" transparent="1" alphatest="on" />
				<ePixmap pixmap="skin_default/buttons/key_text.png" position="290,5" zPosition="4" size="35,25" alphatest="on" transparent="1" />
			</screen>"""
	else:
		skin = """
			<screen name="ImageManagerMenu" position="center,center" size="500,285" title="Image Manager Setup">
				<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
				<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
				<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
				<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
				<widget name="config" position="10,45" size="480,150" scrollbarMode="showOnDemand" />
				<widget name="HelpWindow" pixmap="skin_default/vkey_icon.png" position="165,300" zPosition="1" size="500,285" transparent="1" alphatest="on" />
				<ePixmap pixmap="skin_default/buttons/key_text.png" position="290,5" zPosition="4" size="35,25" alphatest="on" transparent="1" />
			</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.skin = ImageManagerMenu.skin
		self.skinName = "ImageManagerMenu"
		Screen.setTitle(self, _("Image Manager Setup"))
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self.createSetup()
		
		self["actions"] = ActionMap(['ColorActions', 'VirtualKeyboardActions'],
		{
			"red": self.keyCancel,
			"green": self.keySave,
			'showVirtualKeyboard': self.KeyText
		}, -2)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))

	def createSetup(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if pathExists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.imagemanager.backuplocation.setChoices(imparts)
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Backup Location"), config.imagemanager.backuplocation))
		self.list.append(getConfigListEntry(_("Folder prefix"), config.imagemanager.folderprefix))
		self.list.append(getConfigListEntry(_("Schedule Backups"), config.imagemanager.schedule))
		if config.imagemanager.schedule.value:
			self.list.append(getConfigListEntry(_("Time of Backup to start"), config.imagemanager.scheduletime))
			self.list.append(getConfigListEntry(_("Repeat how often"), config.imagemanager.repeattype))
		self["config"].list = self.list
		self["config"].setList(self.list)

	# for summary:
	def changedEntry(self):
		if self["config"].getCurrent()[0] == "Schedule Backups":
			self.createSetup()
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def KeyText(self):
		if self['config'].getCurrent():
			if self['config'].getCurrent()[0] == "Folder prefix":
				from Screens.VirtualKeyBoard import VirtualKeyBoard
				self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title = self["config"].getCurrent()[0], text = self["config"].getCurrent()[1].getValue())

	def VirtualKeyBoardCallback(self, callback = None):
		if callback is not None and len(callback):
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

	def saveAll(self):
		for x in self["config"].list:
			x[1].save()
		configfile.save()

	# keySave and keyCancel are just provided in case you need them.
	# you have to call them by yourself.
	def keySave(self):
		self.saveAll()
		self.close()
	
	def cancelConfirm(self, result):
		if not result:
			return

		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def keyCancel(self):
		if self["config"].isChanged():
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close()

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
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, backupclock[0], backupclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def backupupdate(self, atLeast = 0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		#print '[ImageManager] BACKUP TIME',BackupTime
		#print '[ImageManager] NOW TIME',now
		#print '[ImageManager] ATLEAST',atLeast
		#print '[ImageManager] NOW + ATLEAST', (now + atLeast)
		#print '[ImageManager] BACKUP TIME - NOW', (BackupTime - now)
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				if config.imagemanager.repeattype.value == "daily":
					BackupTime += 24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 24*3600
					#BackupTime += 8*60
					#print '[ImageManager] BACKUP TIME 2:',BackupTime
					#print '[ImageManager] NOW 2:',now
					#while (int(BackupTime)-30) < now:
						#print '[ImageManager] YES BT is Less Now'
						#BackupTime += 8*60
						#print '[ImageManager] BACKUP TIME 2:',BackupTime
				elif config.imagemanager.repeattype.value == "weekly":
					BackupTime += 7*24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 7*24*3600
				elif config.imagemanager.repeattype.value == "monthly":
					BackupTime += 30*24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 30*24*3600
			next = BackupTime - now
			self.backuptimer.startLongTimer(next)
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
			if not inStandby:
				message = _("Your box is about to run a full image backup, this can take about 6 minutes to complete,\ndo you want to allow this?")
				ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle('Scheduled Backup.')
			else:
				print "[ImageManager] in Standby, so just running backup", strftime("%c", localtime(now))
				self.doBackup(True)
		else:
			print '[ImageManager] Where are not close enough', strftime("%c", localtime(now))
			self.backupupdate(60)
					
	def doBackup(self, answer):
		now = int(time())
		if answer is False:
			if config.imagemanager.backupretrycount.value < 2:
				print '[ImageManager] Number of retries',config.imagemanager.backupretrycount.value
				print "[ImageManager] Backup delayed."
				repeat = config.imagemanager.backupretrycount.value
				repeat += 1
				config.imagemanager.backupretrycount.value = repeat
				BackupTime = now + (int(config.imagemanager.backupretry.value) * 60)
				print "[ImageManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
				self.backuptimer.startLongTimer(int(config.imagemanager.backupretry.value) * 60)
			else:
				atLeast = 60
				print "[ImageManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout = 10)
				config.imagemanager.backupretrycount.value = 0
				self.backupupdate(atLeast)
		else:
			print "[ImageManager] Running Backup", strftime("%c", localtime(now))
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			self.close()

class ImageBackup(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.RamChecked = False
		self.SwapCreated = False
		self.Stage1Completed = False
		self.Stage2Completed = False

	def createBackupJob(self):
		job = Components.Task.Job(_("ImageManager"))

		task = Components.Task.PythonTask(job, _("Setting Up..."))
		task.work = self.JobStart
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Checking Free RAM.."), timeoutCount=1)
		task.check = lambda: self.RamChecked
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Creating Swap.."), timeoutCount=20)
		task.check = lambda: self.SwapCreated
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Creating Backup Files..."))
		task.work = self.doBackup1
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Creating Backup Files..."), timeoutCount=600)
		task.check = lambda: self.Stage1Completed
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Moving to Backup Location..."))
		task.work = self.doBackup2
		task.weighting = 1

		task = Components.Task.ConditionTask(job, _("Moving to Backup Location..."), timeoutCount=600)
		task.check = lambda: self.Stage2Completed
		task.weighting = 1

		task = Components.Task.PythonTask(job, _("Backup Complete..."))
		task.work = self.BackupComplete
		task.weighting = 1

		return job

	def JobStart(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if pathExists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.imagemanager.backuplocation.setChoices(imparts)

		if config.imagemanager.backuplocation.value.startswith('/media/net/'):
			mount1 = config.imagemanager.backuplocation.value.replace('/','')
			mount1 = mount1.replace('medianet','/media/net/')
			mount = config.imagemanager.backuplocation.value, mount1
		else:
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value
		hdd = '/media/hdd/','/media/hdd/'
		if mount not in config.imagemanager.backuplocation.choices.choices:
			if hdd in config.imagemanager.backuplocation.choices.choices:
				config.imagemanager.backuplocation.value = '/media/hdd/'
				config.imagemanager.backuplocation.save
				self.BackupDevice = config.imagemanager.backuplocation.value
				print "[ImageManager] Device: " + self.BackupDevice
				self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
				print "[ImageManager] Directory: " + self.BackupDirectory
				print "The chosen location does not exist, using /media/hdd"
			else:
				print "Device: None available"
		else:
			self.BackupDevice = config.imagemanager.backuplocation.value
			print "[ImageManager] Device: " + self.BackupDevice
			self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
			print "[ImageManager] Directory: " + self.BackupDirectory

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
		except Exception,e:
			print str(e)
			print "Device: " + config.imagemanager.backuplocation.value + ", i don't seem to have write access to this device."

		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail)/(1024*1024)
		if int(free) < 200:
			self.session.open(MessageBox, _("The backup location does not have enough freespace."), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.MemCheck()

	def MemCheck(self):
		self.MemCheckConsole = Console()
		cmd = 'free | grep Total | tr -s " " | cut -d " " -f 4'
		self.MemCheckConsole.ePopen(cmd, self.MemCheck1)

	def MemCheck1(self, result, retval, extra_args = None):
		if retval == 0:
			if int(result) < 3000:
				if not config.imagemanager.backuplocation.value.startswith('/media/net/'):
					print '[ImageManager] Stage1: Creating Swapfile.'
					self.RamChecked = True
					self.MemCheck2()
				else:
					print '[ImageManager] Sorry, not enough free ram found, and no phyical devices attached'
					self.session.open(MessageBox, _("Sorry, not enough free ram found, and no phyical devices attached. Can't create Swapfile on network mounts, unable to make backup"), MessageBox.TYPE_INFO, timeout = 10)
					if config.imagemanager.schedule.value:
						atLeast = 60
						autoImageManagerTimer.backupupdate(atLeast)
					else:
						autoImageManagerTimer.backupstop()
			else:
				print '[ImageManager] Stage1: Found Enough Ram'
				self.RamChecked = True
				self.SwapCreated = True
		else:
			print '[ImageManager] Stage1: Free Ram chack fail.'
			if config.imagemanager.schedule.value:
				atLeast = 60
				autoImageManagerTimer.backupupdate(atLeast)
			else:
				autoImageManagerTimer.backupstop()

	def MemCheck2(self):
		self.MemCheckConsole = Console()
		cmd = "dd if=/dev/zero of=" + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup bs=1024 count=61440"
		self.MemCheckConsole.ePopen(cmd, self.MemCheck3)

	def MemCheck3(self, result, retval, extra_args = None):
		if retval == 0:
			self.MemCheckConsole = Console()
			cmd = "mkswap " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"
			self.MemCheckConsole.ePopen(cmd, self.MemCheck4)

	def MemCheck4(self, result, retval, extra_args = None):
		if retval == 0:
			self.MemCheckConsole = Console()
			cmd = "swapon " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"
			self.MemCheckConsole.ePopen(cmd, self.MemCheck5)

	def MemCheck5(self, result, retval, extra_args = None):
		self.SwapCreated = True

	def doBackup1(self):
		self.BackupConsole = Console()
		print '[ImageManager] Stage1: Creating tmp folders.'
		self.BackupDate_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		self.BackupDatetmp = self.BackupDate_stdout.read()
		self.BackupDate = self.BackupDatetmp.rstrip('\n')
		self.ImageVersion_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		self.ImageVersiontmp = self.ImageVersion_stdout.read()
		self.ImageVersion = self.BackupDatetmp.rstrip('\n')
#		OPTIONS=' --eraseblock=0x20000 -n -l'
		MKFS='/usr/bin/mkfs.jffs2'
		NANDDUMP='/usr/bin/nanddump'
		if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi'):
			rmtree(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi')
		mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi', 0777)
		if path.exists('/tmp/' + config.imagemanager.folderprefix.value + '-bi/root'):
			system('umount /tmp/' + config.imagemanager.folderprefix.value + '-bi/root')
		if path.exists('/tmp/' + config.imagemanager.folderprefix.value + '-bi/boot'):
			system('umount /tmp/' + config.imagemanager.folderprefix.value + '-bi/boot')
		if path.exists('/tmp/' + config.imagemanager.folderprefix.value + '-bi'):
			rmtree('/tmp/' + config.imagemanager.folderprefix.value + '-bi')
		mkdir('/tmp/' + config.imagemanager.folderprefix.value + '-bi', 0777)
		mkdir('/tmp/' + config.imagemanager.folderprefix.value + '-bi/root', 0777)
		mkdir('/tmp/' + config.imagemanager.folderprefix.value + '-bi/boot', 0777)
		if config.misc.boxtype.value == "vusolo" or config.misc.boxtype.value == "vuduo":
			print '[ImageManager] Stage1: Creating backup folders.'
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus', 0777)
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu',''), 0777)
			print '[ImageManager] Stage1: Making Image.'
			self.commands = []
			self.commands.append("mount -t jffs2 /dev/mtdblock0 /tmp/" + config.imagemanager.folderprefix.value + "-bi/root")
			self.commands.append("mount -t jffs2 /dev/mtdblock2 /tmp/" + config.imagemanager.folderprefix.value + "-bi/boot")
			self.commands.append(MKFS + ' --root=/tmp/' + config.imagemanager.folderprefix.value + '-bi/boot --faketime --output=' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/boot.jffs2 --eraseblock=0x20000 -n -l')
			self.commands.append(MKFS + ' --root=/tmp/' + config.imagemanager.folderprefix.value + '-bi/root --faketime --output=' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/root.jffs2 --eraseblock=0x20000 -n -l')
			self.commands.append(NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/vmlinux.gz')
			self.BackupConsole.eBatch(self.commands, self.Stage1Complete, debug=True)
		elif config.misc.boxtype.value == "vuuno" or config.misc.boxtype.value == "vuultimo":
			print '[ImageManager] Stage1: Creating backup folders.'
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus', 0777)
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu',''), 0777)
			print '[ImageManager] Stage1: Making Image.'
			self.commands = []
			self.commands.append("mount -t jffs2 /dev/mtdblock0 /tmp/" + config.imagemanager.folderprefix.value + "-bi/root")
			self.commands.append("mount -t jffs2 /dev/mtdblock2 /tmp/" + config.imagemanager.folderprefix.value + "-bi/boot")
			self.commands.append(MKFS + ' --root=/tmp/' + config.imagemanager.folderprefix.value + '-bi/boot --faketime --output=' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/boot.jffs2 --eraseblock=0x20000 -n -l')
			self.commands.append(MKFS + ' --root=/tmp/' + config.imagemanager.folderprefix.value + '-bi/root --faketime --output=' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/root.jffs2 --eraseblock=0x20000 -n -l')
			self.commands.append(NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/vmlinux.gz')
			self.commands.append(NANDDUMP + ' /dev/mtd3 -o -b > ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/splash.bin')
			self.BackupConsole.eBatch(self.commands, self.Stage1Complete, debug=True)
		elif config.misc.boxtype.value == "et9000" or config.misc.boxtype.value == "et5000":
			print '[ImageManager] Stage1: Creating backup Folders.'
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value, 0777)
			print '[ImageManager] Stage1: Making Image.'
			self.commands = []
			self.commands.append("mount -t jffs2 /dev/mtdblock2 /tmp/" + config.imagemanager.folderprefix.value + "-bi/boot")
			self.commands.append("mount -t jffs2 /dev/mtdblock3 /tmp/" + config.imagemanager.folderprefix.value + "-bi/root")
			self.commands.append(MKFS + ' --root=/tmp/' + config.imagemanager.folderprefix.value + '-bi/boot --faketime --output=' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/boot.jffs2 --eraseblock=0x20000 -n -l')
			self.commands.append(MKFS + ' --root=/tmp/' + config.imagemanager.folderprefix.value + '-bi/root --faketime --output=' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/root.jffs2 --eraseblock=0x20000 -n -l')
			self.commands.append(NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/vmlinux.gz')
			self.BackupConsole.eBatch(self.commands, self.Stage1Complete, debug=True)
			print '{ImageManager] Stage1: Complete.'

	def Stage1Complete(self, extra_args):
		if len(self.BackupConsole.appContainers) == 0:
			self.Stage1Completed = True
			print '[ImageManager] Stage1: Complete.'

	def doBackup2(self):
		print '[ImageManager] Stage2: Unmounting tmp system'
		if path.exists('/tmp/' + config.imagemanager.folderprefix.value + '-bi/root'):
			system('umount /tmp/' + config.imagemanager.folderprefix.value + '-bi/root')
		if path.exists('/tmp/' + config.imagemanager.folderprefix.value + '-bi/boot'):
			system('umount /tmp/' + config.imagemanager.folderprefix.value + '-bi/boot')
		if path.exists('/tmp/' + config.imagemanager.folderprefix.value + '-bi'):
			rmtree('/tmp/' + config.imagemanager.folderprefix.value + '-bi')
		print '[ImageManager] Stage2: Moving from tmp to backup folders'
		if config.misc.boxtype.value == "vusolo" or config.misc.boxtype.value == "vuduo" or config.misc.boxtype.value == "vuuno" or config.misc.boxtype.value == "vuultimo":
			move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/root.jffs2', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/root_cfe_auto.jffs2')
			move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/boot.jffs2', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/boot_cfe_auto.jffs2')
			move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/vmlinux.gz', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/kernel_cfe_auto.bin')
			if config.misc.boxtype.value == "vuuno" or config.misc.boxtype.value == "vuultimo":
				move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/splash.bin', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/splash_cfe_auto.bin')
		elif config.misc.boxtype.value == "et9000" or config.misc.boxtype.value == "et5000":
			move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/root.jffs2', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/rootfs.bin')
			move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/boot.jffs2', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/boot.bin')
			move(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi/vmlinux.gz', self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/kernel.bin')
			fileout = open(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/noforce', 'w')
			line = "rename this file to 'force' to force an update without confirmation"
			fileout.write(line)
			fileout.close()
			fileout = open(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + 'imageversion', 'w')
			line = "ViX-" + self.ImageVersion
			fileout.write(line)
			fileout.close()
		print '[ImageManager] Stage2: Removing Swap.'
		if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi'):
			rmtree(self.BackupDirectory + config.imagemanager.folderprefix.value + '-bi')
		if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup'):
			system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
			remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
		if (fileExists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/root_cfe_auto.jffs2') and fileExists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/boot_cfe_auto.jffs2') and fileExists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/vuplus/' + config.misc.boxtype.value.replace('vu','') + '/kernel_cfe_auto.bin')) or (fileExists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/rootfs.bin') and fileExists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/boot.bin') and fileExists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate + '/' + config.misc.boxtype.value + '/kernel.bin')):
			print '{ImageManager] Stage2: Image created in ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate
			self.Stage2Complete()
		else:
			print "{ImageManager] Stage2: Image creation failed - e. g. wrong backup destination or no space left on backup device"
			self.Stage2Complete()

	def Stage2Complete(self):
		self.Stage2Completed = True
		print '[ImageManager] Stage2: Complete.'
	
	def BackupComplete(self):
		if config.imagemanager.schedule.value:
			atLeast = 60
			autoImageManagerTimer.backupupdate(atLeast)
		else:
			autoImageManagerTimer.backupstop()
