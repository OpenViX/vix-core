from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Pixmap import MultiPixmap, Pixmap
from Components.config import config, ConfigYesNo, ConfigSubsection, getConfigListEntry, ConfigSelection, ConfigText, ConfigClock, ConfigNumber, NoSave
from Components.ConfigList import ConfigListScreen
from Components.Harddisk import harddiskmanager
from Components.Language import language
from Screens.Screen import Screen
from Screens.Console import Console
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
		self["title"] = Label(_("Image Manager"))
		self['lab1'] = Label()
		self["backupstatus"] = Label()
		self.emlist = []
		self.populate_List()
		self['list'] = MenuList(self.emlist)
		self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
			{
				'cancel': self.close,
				'red': self.close,
				'green': self.keyBackup,
				'yellow': self.keyResstore,
				'blue': self.keyDelete,
				"menu": self.createSetup,
			}, -1)

		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("New Backup"))
		self["key_yellow"] = Button(_("Restore"))
		self["key_blue"] = Button(_("Delete"))

	def populate_List(self):
		parts = []
		for p in harddiskmanager.getMountedPartitions():
			d = path.normpath(p.mountpoint)
			if pathExists(p.mountpoint) and p.mountpoint != "/":
				parts.append((d, p.mountpoint))
		if len(parts):
			config.vixsettings.imagemanager_backuplocation = ConfigSelection(default = "/media/hdd/", choices = parts)

		try:
			file = open('/etc/image-version', 'r')
			lines = file.readlines()
			file.close()
			for x in lines:
				splitted = x.split('=')
				if splitted[0] == "box_type":
					folderprefix = splitted[1].replace('\n','') # 0 = release, 1 = experimental
		except:
			folderprefix=""
		config.vixsettings.imagemanager_folderprefix = ConfigText(default=folderprefix, fixed_size=False)

		if not path.exists(config.vixsettings.imagemanager_backuplocation.value):
			self.BackupDirectory = '/media/hdd/imagebackups/'
			self['lab1'].setText(_("Device: /media/hdd") + _("\nSelect an image to Restore / Delete:"))
			self.session.open(MessageBox, _("The chosen location does not exist, using /media/hdd"), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.BackupDirectory = config.vixsettings.imagemanager_backuplocation.value + 'imagebackups/'
			self['lab1'].setText(_("Device: ") + config.vixsettings.imagemanager_backuplocation.value + _("\nSelect an image to Restore / Delete:"))
		try:
			file = open('/etc/image-version', 'r')
			lines = file.readlines()
			file.close()
			for x in lines:
				splitted = x.split('=')
				if splitted[0] == "box_type":
					self.boxtype = splitted[1].replace('\n','') # 0 = release, 1 = experimental
		except:
			self.boxtype="not detected"

		if not path.exists(self.BackupDirectory):
			mkdir(self.BackupDirectory, 0755)
		if path.exists(self.BackupDirectory + 'swapfile_backup'):
			system('swapoff ' + self.BackupDirectory + 'swapfile_backup')
			remove(self.BackupDirectory + 'swapfile_backup')
		images = listdir(self.BackupDirectory)
		del self.emlist[:]
		for fil in images:
			self.emlist.append(fil)
		self.emlist.sort()	
		if BackupTime > 0:
			backuptext = _("Next Backup: ") + strftime("%c", localtime(BackupTime))
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))

	def createSetup(self):
		self.session.openWithCallback(self.doneConfiguring, ImageManagerMenu)

	def doneConfiguring(self):
		now = int(time())
		if config.vixsettings.imagemanager_schedule.value:
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

	def keyBackup(self):
		if self.boxtype == "vuuno" or self.boxtype == "vuultimo" or self.boxtype == "vusolo" or self.boxtype == "vuduo" or self.boxtype == "et9000" or self.boxtype == "et5000":
			message = _("Are you ready to create a backup image ?")
			ybox = self.session.openWithCallback(self.BackupMemCheck, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Backup Confirmation"))
		else:
			self.session.open(MessageBox, _("Sorry you box is not yet compatible."), MessageBox.TYPE_INFO, timeout = 10)
 
	def keyResstore(self):
		self.sel = self['list'].getCurrent()
		if not config.crash.enabledebug.value:
			if (self.boxtype == "vuuno" and path.exists(self.BackupDirectory + self.sel + '/vuplus/uno')) or (self.boxtype == "vuultimo" and path.exists(self.BackupDirectory + self.sel + '/vuplus/ultimo')) or (self.boxtype == "vusolo" and path.exists(self.BackupDirectory + self.sel + '/vuplus/solo')) or (self.boxtype == "vuduo" and path.exists(self.BackupDirectory + self.sel + '/vuplus/vuduo')) or (self.boxtype == "et9000" and path.exists(self.BackupDirectory + self.sel + '/et9000')) or (self.boxtype == "et5000" and path.exists(self.BackupDirectory + self.sel + '/et5000')):
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

	def keyDelete(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to delete this backup:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDelete, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Remove Confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to delete."), MessageBox.TYPE_INFO, timeout = 10)
				
	def BackupMemCheck(self,answer):
		if answer is True:
			self.BackupDevice = self.BackupDirectory.replace('/imagebackups','')
			s = statvfs(self.BackupDevice)
			free = (s.f_bsize * s.f_bavail)/(1024*1024)
			if int(free) < 200:
				self.session.open(MessageBox, _("The backup location does not have enough freespace."), MessageBox.TYPE_INFO, timeout = 10)
			else:
				try:
					memcheck_stdout = popen('free | grep Total | tr -s " " | cut -d " " -f 4', "r")
					memcheck = memcheck_stdout.read()
					if int(memcheck) < 61440:
						mycmd1 = "echo '************************************************************************'"
						mycmd2 = "echo 'Creating swapfile'"
						mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + "/swapfile_backup bs=1024 count=61440"
						mycmd4 = "mkswap " + self.BackupDirectory + "/swapfile_backup"
						mycmd5 = "swapon " + self.BackupDirectory + "/swapfile_backup"
						mycmd6 = "echo '************************************************************************'"
						self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doBackup,closeOnSuccess = True)
					else:
						self.doBackup()
				except:
					mycmd1 = "echo '************************************************************************'"
					mycmd2 = "echo 'Creating swapfile'"
					mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + "/swapfile_backup bs=1024 count=61440"
					mycmd4 = "mkswap " + self.BackupDirectory + "/swapfile_backup"
					mycmd5 = "swapon " + self.BackupDirectory + "/swapfile_backup"
					mycmd6 = "echo '************************************************************************'"
					self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doBackup,closeOnSuccess = True)
	
	def doBackup(self):
		self.BackupDate_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		self.BackupDatetmp = self.BackupDate_stdout.read()
		self.BackupDate = self.BackupDatetmp.rstrip('\n')
		self.ImageVersion_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		self.ImageVersiontmp = self.ImageVersion_stdout.read()
		self.ImageVersion = self.BackupDatetmp.rstrip('\n')
#		OPTIONS=' --eraseblock=0x20000 -n -l'
		MKFS='/usr/bin/mkfs.jffs2'
		NANDDUMP='/usr/bin/nanddump'
		if path.exists(self.BackupDirectory + 'bi'):
			rmtree(self.BackupDirectory + 'bi')
		mkdir(self.BackupDirectory + 'bi', 0777)
		if path.exists('/tmp/bi'):
			rmtree('/tmp/bi')
		mkdir('/tmp/bi', 0777)
		mkdir('/tmp/bi/root', 0777)
		mkdir('/tmp/bi/boot', 0777)

		if self.boxtype == "vusolo" or self.boxtype == "vuduo":
			if path.exists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus'):
				rmtree(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus')
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus', 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu',''), 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + self.boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock0 /tmp/bi/root"
			mycmd5 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + self.BackupDirectory + 'bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating System root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + self.BackupDirectory + 'bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating Kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + 'bi/vmlinux.gz'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11], finishedCallback=self.doBackup2,closeOnSuccess = True)

		elif self.boxtype == "vuuno" or self.boxtype == "vuultimo":
			if path.exists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus'):
				rmtree(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus')
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus', 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu',''), 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + self.boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock0 /tmp/bi/root"
			mycmd5 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + self.BackupDirectory + 'bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating System root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + self.BackupDirectory + 'bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating Kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + 'bi/vmlinux.gz'
			mycmd12 = "echo 'Creating bootsplash'"
			mycmd13 = NANDDUMP + ' /dev/mtd3 -o -b > ' + self.BackupDirectory + 'bi/splash.bin'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13], finishedCallback=self.doBackup2,closeOnSuccess = True)
		elif self.boxtype == "et9000" or self.boxtype == "et5000":
			if path.exists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate):
				rmtree(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype, 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Xtrend " + self.boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd5 = "mount -t jffs2 /dev/mtdblock3 /tmp/bi/root"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + self.BackupDirectory + 'bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating System root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + self.BackupDirectory + 'bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating Kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + 'bi/vmlinux.gz'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11], finishedCallback=self.doBackup2,closeOnSuccess = True)

	def doBackup2(self):
		if self.boxtype == "vusolo" or self.boxtype == "vuduo" or self.boxtype == "vuuno" or self.boxtype == "vuultimo":
			move(self.BackupDirectory + 'bi/root.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/root_cfe_auto.jffs2')
			move(self.BackupDirectory + 'bi/boot.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/boot_cfe_auto.jffs2')
			move(self.BackupDirectory + 'bi/vmlinux.gz', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/kernel_cfe_auto.bin')
			if self.boxtype == "vuuno" or self.boxtype == "vuultimo":
				move(self.BackupDirectory + 'bi/splash.bin', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/splash_cfe_auto.bin')
			system('umount /tmp/bi/root')
			system('umount /tmp/bi/boot')
			rmtree('/tmp/bi')
			rmtree(self.BackupDirectory + 'bi')
			if path.exists(self.BackupDirectory + 'swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + 'swapfile_backup')
				remove(self.BackupDirectory + 'swapfile_backup')
			if fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/root_cfe_auto.jffs2') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/boot_cfe_auto.jffs2') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/kernel_cfe_auto.bin'):
				self.session.open(MessageBox, _("Image created in " + self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Image creation failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
		elif self.boxtype == "et9000" or self.boxtype == "et5000":
			move(self.BackupDirectory + 'bi/root.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/rootfs.bin')
			move(self.BackupDirectory + 'bi/boot.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/boot.bin')
			move(self.BackupDirectory + 'bi/vmlinux.gz', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/kernel.bin')
			fileout = open(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/noforce', 'w')
			line = "rename this file to 'force' to force an update without confirmation"
			fileout.write(line)
			fileout.close()
			fileout = open(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/imageversion', 'w')
			line = "ViX-" + self.ImageVersion
			fileout.write(line)
			fileout.close()
			system('umount /tmp/bi/root')
			system('umount /tmp/bi/boot')
			rmtree('/tmp/bi')
			rmtree(self.BackupDirectory + 'bi')
			if path.exists(self.BackupDirectory + 'swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + 'swapfile_backup')
				remove(self.BackupDirectory + 'swapfile_backup')
			if fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/rootfs.bin') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/boot.bin') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/kernel.bin'):
				self.session.open(MessageBox, _("Image created in " + self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Image creation failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
		self.populate_List()

	def RestoreMemCheck(self,answer):
		if answer is True:
			try:
				memcheck_stdout = popen('free | grep Total | tr -s " " | cut -d " " -f 4', "r")
				memcheck = memcheck_stdout.read()
				if int(memcheck) < 61440:
					mycmd1 = "echo '************************************************************************'"
					mycmd2 = "echo 'Creating swapfile'"
					mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + "/swapfile_backup bs=1024 count=61440"
					mycmd4 = "mkswap " + self.BackupDirectory + "/swapfile_backup"
					mycmd5 = "swapon " + self.BackupDirectory + "/swapfile_backup"
					mycmd6 = "echo '************************************************************************'"
					self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doResstore,closeOnSuccess = True)
				else:
					self.RestoreMemCheck()
			except:
				mycmd1 = "echo '************************************************************************'"
				mycmd2 = "echo 'Creating swapfile'"
				mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + "/swapfile_backup bs=1024 count=61440"
				mycmd4 = "mkswap " + self.BackupDirectory + "/swapfile_backup"
				mycmd5 = "swapon " + self.BackupDirectory + "/swapfile_backup"
				mycmd6 = "echo '************************************************************************'"
				self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doResstore,closeOnSuccess = True)

	def doResstore(self):
		NANDWRITE='/usr/bin/nandwrite'
		selectedimage = self.sel
		if self.boxtype == "vusolo" or self.boxtype == "vuduo":
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + self.boxtype +  " detected'"
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
			mycmd13 = NANDWRITE + ' -p -q /dev/mtd2 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/boot_cfe_auto.jffs2'
			mycmd14 = "echo 'Erasing Root aera.'"
			mycmd15 = 'flash_eraseall -j -q /dev/mtd0'
			mycmd16 = "echo 'Flasing Root to NAND.'"
			mycmd17 = NANDWRITE + ' -p -q /dev/mtd0 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/root_cfe_auto.jffs2'
			mycmd18 = "echo 'Erasing Kernel aera.'"
			mycmd19 = 'flash_eraseall -j -q /dev/mtd1'
			mycmd20 = "echo 'Flasing Kernel to NAND.'"
			mycmd21 = NANDWRITE + ' -p -q /dev/mtd1 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/kernel_cfe_auto.bin'
			mycmd22 = "echo ' '"
			mycmd23 = "echo 'Flasing Complete\nRebooting.'"
			mycmd24 = "sleep 2"
			mycmd25 = "/sbin/shutdown.sysvinit -r now"
			self.session.open(Console, title='Flashing NAND...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22, mycmd23, mycmd24, mycmd25],closeOnSuccess = True)
		elif self.boxtype == "vuuno" or self.boxtype == "vuultimo":
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + self.boxtype +  " detected'"
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
			mycmd13 = NANDWRITE + ' -p -q /dev/mtd3 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/splash_cfe_auto.bin'
			mycmd14 = "echo 'Erasing Boot aera.'"
			mycmd15 = 'flash_eraseall -j -q /dev/mtd2'
			mycmd16 = "echo 'Flasing Boot to NAND.'"
			mycmd17 = NANDWRITE + ' -p -q /dev/mtd2 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/boot_cfe_auto.jffs2'
			mycmd18 = "echo 'Erasing Root aera.'"
			mycmd19 = 'flash_eraseall -j -q /dev/mtd0'
			mycmd20 = "echo 'Flasing Root to NAND.'"
			mycmd21 = NANDWRITE + ' -p -q /dev/mtd0 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/root_cfe_auto.jffs2'
			mycmd22 = "echo 'Erasing Kernel aera.'"
			mycmd23 = 'flash_eraseall -j -q /dev/mtd1'
			mycmd24 = "echo 'Flasing Kernel to NAND.'"
			mycmd25 = NANDWRITE + ' -p -q /dev/mtd1 ' + self.BackupDirectory + selectedimage + '/vuplus/' + self.boxtype.replace('vu','') + '/kernel_cfe_auto.bin'
			mycmd26 = "echo ' '"
			mycmd27 = "echo 'Flasing Complete\nRebooting.'"
			mycmd28 = "sleep 2"
			mycmd29 = "/sbin/shutdown.sysvinit -r now"
			self.session.open(Console, title='Flashing NAND...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22, mycmd23, mycmd24, mycmd25, mycmd26, mycmd27, mycmd28, mycmd29],closeOnSuccess = True)
		elif self.boxtype == "et9000" or self.boxtype == "et5000":
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Xtrend " + self.boxtype +  " detected'"
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
			mycmd13 = NANDWRITE + ' -p -q /dev/mtd2 ' + self.BackupDirectory + selectedimage + '/' + self.boxtype + '/boot.bin'
			mycmd14 = "echo 'Erasing Root aera.'"
			mycmd15 = 'flash_eraseall -j -q /dev/mtd3'
			mycmd16 = "echo 'Flasing Root to NAND.'"
			mycmd17 = NANDWRITE + ' -p -q /dev/mtd3 ' + self.BackupDirectory + selectedimage + '/' + self.boxtype + '/rootfs.bin'
			mycmd18 = "echo 'Erasing Kernel aera.'"
			mycmd19 = 'flash_eraseall -j -q /dev/mtd1'
			mycmd20 = "echo 'Flasing Kernel to NAND.'"
			mycmd21 = NANDWRITE + ' -p -q /dev/mtd1 ' + self.BackupDirectory + selectedimage + '/' + self.boxtype + '/kernel.bin'
			mycmd22 = "echo ' '"
			mycmd23 = "echo 'Flasing Complete\nRebooting.'"
			mycmd24 = "sleep 2"
			mycmd25 = "/sbin/shutdown.sysvinit -r now"
			self.session.open(Console, title='Flashing NAND...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22, mycmd23, mycmd24, mycmd25],closeOnSuccess = True)
				
	def doDelete(self, answer):
		if answer is True:
			self.sel = self['list'].getCurrent()
			selectedimage = self.sel
			rmtree(self.BackupDirectory + selectedimage)
		self.populate_List()

	def myclose(self):
		self.close()
		

config.vixsettings.imagemanager_schedule = ConfigYesNo(default = False)
config.vixsettings.imagemanager_scheduletime = ConfigClock(default = 0) # 1:00
config.vixsettings.imagemanager_repeattype = ConfigSelection(default = "daily", choices = [("daily", _("Daily")), ("weekly", _("Weely")), ("monthly", _("30 Days"))])
config.vixsettings.imagemanager_backupretry = ConfigNumber(default = 30)
config.vixsettings.imagemanager_backupretrycount = NoSave(ConfigNumber(default = 0))

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
		self["title"] = Label(_("Image Manager Setup"))
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self.createSetup()
		
		self["actions"] = ActionMap(["SetupActions", 'ColorActions', 'VirtualKeyboardActions'],
		{
			"cancel": self.keyCancel,
			"save": self.keySaveNew,
			'showVirtualKeyboard': self.vkeyb
		}, -2)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))

	def createSetup(self):
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Backup Location"), config.vixsettings.imagemanager_backuplocation))
		self.list.append(getConfigListEntry(_("Folder prefix"), config.vixsettings.imagemanager_folderprefix))
		self.list.append(getConfigListEntry(_("Schedule Backups"), config.vixsettings.imagemanager_schedule))
		if config.vixsettings.imagemanager_schedule.value:
			self.list.append(getConfigListEntry(_("Time of Backup to start"), config.vixsettings.imagemanager_scheduletime))
			self.list.append(getConfigListEntry(_("Repeat how often"), config.vixsettings.imagemanager_repeattype))
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
		self.close()

	def keyCancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def vkeyb(self):
		sel = self['config'].getCurrent()
		if sel:
			self.vkvar = sel[0]
			if self.vkvar == "Folder prefix":
				self.session.openWithCallback(self.UpdateAgain, VirtualKeyBoard, title=self.vkvar, text=config.vixsettings.imagemanager_folderprefix.value)

	def UpdateAgain(self, text):
		self.list = []
		if text is None or text == '':
			text = ''
		if self.vkvar == "Folder prefix":
			config.vixsettings.imagemanager_folderprefix.value = text
		self.list = []
		self.list.append(getConfigListEntry(_("Backup Location"), config.vixsettings.imagemanager_backuplocation))
		self.list.append(getConfigListEntry(_("Folder prefix"), config.vixsettings.imagemanager_folderprefix))
		self.list.append(getConfigListEntry(_("Schedule Backups"), config.vixsettings.imagemanager_schedule))
		if config.vixsettings.imagemanager_schedule.value:
			self.list.append(getConfigListEntry(_("Time of Backup to start"), config.vixsettings.imagemanager__scheduletime))
			self.list.append(getConfigListEntry(_("Repeat how often"), config.vixsettings.imagemanager_repeattype))
		self["config"].list = self.list
		self["config"].setList(self.list)
		return None

class AutoImageManagerTimer:
	def __init__(self, session):
		self.session = session
		self.backuptimer = eTimer() 
		self.backuptimer.callback.append(self.BackuponTimer)
		self.backupactivityTimer = eTimer()
		self.backupactivityTimer.timeout.get().append(self.backupupdatedelay)
		now = int(time())
		global BackupTime
		if config.vixsettings.imagemanager_schedule.value:
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
		backupclock = config.vixsettings.imagemanager_scheduletime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, backupclock[0], backupclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def backupupdate(self, atLeast = 0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				if config.vixsettings.imagemanager_repeattype.value == "daily":
					BackupTime += 24*3600
				elif config.vixsettings.imagemanager_repeattype.value == "weekly":
					BackupTime += 7*24*3600
				elif config.vixsettings.imagemanager_repeattype.value == "monthly":
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
		print "[ImageManager] Backup onTimer occured at", strftime("%c", localtime(now))
		from Screens.Standby import inStandby
		if not inStandby:
			message = _("Your box is about to run a full image backup, this can take about 6 minutes to complete,\ndo you want to allow this?")
			ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
			ybox.setTitle('Scheduled Backup.')
		else:
			print "[ImageManager] in Standby, so just running backup", strftime("%c", localtime(now))
			atLeast = 60
			print "[ImageManager] Running Backup", strftime("%c", localtime(now))
			self.backupupdate(atLeast)
			self.BackupMemCheck()
					
	def doBackup(self, answer):
		now = int(time())
		print 'RETRIES',config.vixsettings.imagemanager_backupretrycount.value
		if config.vixsettings.imagemanager_backupretrycount.value < 2:
			if answer is False:
				print "[ImageManager] Backup delayed."
				repeat = config.vixsettings.imagemanager_backupretrycount.value
				repeat += 1
				config.vixsettings.imagemanager_backupretrycount.value = repeat
				BackupTime = now + (int(config.vixsettings.imagemanager_backupretry.value) * 60)
				print "[ImageManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
				self.backuptimer.startLongTimer(int(config.vixsettings.imagemanager_backupretry.value) * 60)
			else:
				atLeast = 60
				print "[ImageManager] Running Backup", strftime("%c", localtime(now))
				self.backupupdate(atLeast)
				self.BackupMemCheck()
		else:
			atLeast = 60
			print "[ImageManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now))
			self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout = 10)
			config.vixsettings.imagemanager_backupretrycount.value = 0
			self.backupupdate(atLeast)


	def BackupMemCheck(self):
		if not path.exists(config.vixsettings.imagemanager_backuplocation.value):
			self.BackupDirectory = '/media/hdd/imagebackups/'
		else:
			self.BackupDirectory = config.vixsettings.imagemanager_backuplocation.value + '/imagebackups/'
		try:
			file = open('/etc/image-version', 'r')
			lines = file.readlines()
			file.close()
			for x in lines:
				splitted = x.split('=')
				if splitted[0] == "box_type":
					self.boxtype = splitted[1].replace('\n','') # 0 = release, 1 = experimental
		except:
			self.boxtype="not detected"

		if not path.exists(self.BackupDirectory):
			mkdir(self.BackupDirectory, 0755)

		self.BackupDevice = self.BackupDirectory.replace('/imagebackups','')
		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail)/(1024*1024)
		if int(free) < 200:
			self.session.open(MessageBox, _("The backup location does not have enough freespace."), MessageBox.TYPE_INFO, timeout = 10)
		else:
			try:
				memcheck_stdout = popen('free | grep Total | tr -s " " | cut -d " " -f 4', "r")
				memcheck = memcheck_stdout.read()
				if int(memcheck) < 61440:
					mycmd1 = "echo '************************************************************************'"
					mycmd2 = "echo 'Creating swapfile'"
					mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + "/swapfile_backup bs=1024 count=61440"
					mycmd4 = "mkswap " + self.BackupDirectory + "/swapfile_backup"
					mycmd5 = "swapon " + self.BackupDirectory + "/swapfile_backup"
					mycmd6 = "echo '************************************************************************'"
					self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doBackup1,closeOnSuccess = True)
				else:
					self.doBackup()
			except:
				mycmd1 = "echo '************************************************************************'"
				mycmd2 = "echo 'Creating swapfile'"
				mycmd3 = "dd if=/dev/zero of=" + self.BackupDirectory + "/swapfile_backup bs=1024 count=61440"
				mycmd4 = "mkswap " + self.BackupDirectory + "/swapfile_backup"
				mycmd5 = "swapon " + self.BackupDirectory + "/swapfile_backup"
				mycmd6 = "echo '************************************************************************'"
				self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doBackup1,closeOnSuccess = True)
	
	def doBackup1(self):
		self.BackupDate_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		self.BackupDatetmp = self.BackupDate_stdout.read()
		self.BackupDate = self.BackupDatetmp.rstrip('\n')
		self.ImageVersion_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		self.ImageVersiontmp = self.ImageVersion_stdout.read()
		self.ImageVersion = self.BackupDatetmp.rstrip('\n')
#		OPTIONS=' --eraseblock=0x20000 -n -l'
		MKFS='/usr/bin/mkfs.jffs2'
		NANDDUMP='/usr/bin/nanddump'
		if path.exists(self.BackupDirectory + 'bi'):
			rmtree(self.BackupDirectory + 'bi')
		mkdir(self.BackupDirectory + 'bi', 0777)
		if path.exists('/tmp/bi'):
			rmtree('/tmp/bi')
		mkdir('/tmp/bi', 0777)
		mkdir('/tmp/bi/root', 0777)
		mkdir('/tmp/bi/boot', 0777)

		if self.boxtype == "vusolo" or self.boxtype == "vuduo":
			if path.exists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus'):
				rmtree(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus')
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus', 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu',''), 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + self.boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock0 /tmp/bi/root"
			mycmd5 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + self.BackupDirectory + 'bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating System root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + self.BackupDirectory + 'bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating Kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + 'bi/vmlinux.gz'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11], finishedCallback=self.doBackup2,closeOnSuccess = True)

		elif self.boxtype == "vuuno" or self.boxtype == "vuultimo":
			if path.exists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus'):
				rmtree(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus')
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus', 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu',''), 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + self.boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock0 /tmp/bi/root"
			mycmd5 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + self.BackupDirectory + 'bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating System root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + self.BackupDirectory + 'bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating Kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + 'bi/vmlinux.gz'
			mycmd12 = "echo 'Creating bootsplash'"
			mycmd13 = NANDDUMP + ' /dev/mtd3 -o -b > ' + self.BackupDirectory + 'bi/splash.bin'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13], finishedCallback=self.doBackup2,closeOnSuccess = True)
		elif self.boxtype == "et9000" or self.boxtype == "et5000":
			if path.exists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate):
				rmtree(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate, 0777)
			mkdir(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype, 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Xtrend " + self.boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd5 = "mount -t jffs2 /dev/mtdblock3 /tmp/bi/root"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + self.BackupDirectory + 'bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating System root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + self.BackupDirectory + 'bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating Kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + self.BackupDirectory + 'bi/vmlinux.gz'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11], finishedCallback=self.doBackup2,closeOnSuccess = True)

	def doBackup2(self):
		if self.boxtype == "vusolo" or self.boxtype == "vuduo" or self.boxtype == "vuuno" or self.boxtype == "vuultimo":
			move(self.BackupDirectory + 'bi/root.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/root_cfe_auto.jffs2')
			move(self.BackupDirectory + 'bi/boot.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/boot_cfe_auto.jffs2')
			move(self.BackupDirectory + 'bi/vmlinux.gz', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/kernel_cfe_auto.bin')
			if self.boxtype == "vuuno" or self.boxtype == "vuultimo":
				move(self.BackupDirectory + 'bi/splash.bin', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/splash_cfe_auto.bin')
			system('umount /tmp/bi/root')
			system('umount /tmp/bi/boot')
			rmtree('/tmp/bi')
			rmtree(self.BackupDirectory + 'bi')
			if path.exists(self.BackupDirectory + 'swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + 'swapfile_backup')
				remove(self.BackupDirectory + 'swapfile_backup')
			if fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/root_cfe_auto.jffs2') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/boot_cfe_auto.jffs2') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/vuplus/' + self.boxtype.replace('vu','') + '/kernel_cfe_auto.bin'):
				self.session.open(MessageBox, _("Image created in " + self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Image creation failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
		elif self.boxtype == "et9000" or self.boxtype == "et5000":
			move(self.BackupDirectory + 'bi/root.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/rootfs.bin')
			move(self.BackupDirectory + 'bi/boot.jffs2', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/boot.bin')
			move(self.BackupDirectory + 'bi/vmlinux.gz', self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/kernel.bin')
			fileout = open(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/noforce', 'w')
			line = "rename this file to 'force' to force an update without confirmation"
			fileout.write(line)
			fileout.close()
			fileout = open(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/imageversion', 'w')
			line = "ViX-" + self.ImageVersion
			fileout.write(line)
			fileout.close()
			system('umount /tmp/bi/root')
			system('umount /tmp/bi/boot')
			rmtree('/tmp/bi')
			rmtree(self.BackupDirectory + 'bi')
			if path.exists(self.BackupDirectory + 'swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + 'swapfile_backup')
				remove(self.BackupDirectory + 'swapfile_backup')
			if fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/rootfs.bin') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/boot.bin') and fileExists(self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate + '/' + self.boxtype + '/kernel.bin'):
				self.session.open(MessageBox, _("Image created in " + self.BackupDirectory + config.vixsettings.imagemanager_folderprefix.value + '-' + self.BackupDate), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Image creation failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
