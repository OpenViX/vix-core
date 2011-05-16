from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.Console import Console
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Components.Button import Button
from Components.ScrollLabel import ScrollLabel
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Pixmap import MultiPixmap, Pixmap
from Components.config import config, ConfigYesNo, ConfigSubsection, getConfigListEntry, ConfigSelection, ConfigText, ConfigInteger
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Components.PluginComponent import plugins
from Components.PluginList import *
from Components.Harddisk import harddiskmanager
from Components.Language import language
from Components.SelectionList import SelectionList
from Tools.Directories import pathExists, fileExists, resolveFilename,SCOPE_LANGUAGE, SCOPE_PLUGINS, SCOPE_CURRENT_PLUGIN, SCOPE_CURRENT_SKIN, SCOPE_METADIR
from Tools.LoadPixmap import LoadPixmap
from enigma import eConsoleAppContainer, eTimer, quitMainloop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, eListboxPythonMultiContent, eListbox, gFont, getDesktop, ePicLoad
from ServiceReference import ServiceReference
from os import path, system, unlink, stat, mkdir, popen, makedirs, chdir, getcwd, listdir, rename, remove, access, W_OK, R_OK, F_OK, environ
import datetime, time, gettext
from shutil import rmtree, move, copy

config.plugins.VIXSettings  = ConfigSubsection()
config.plugins.VIXSettings.backuplocation = ConfigText(default = '/media/hdd', visible_width = 50, fixed_size = False)

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
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 20" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,300" scrollbarMode="showOnDemand" />
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""


	def __init__(self, session):
		Screen.__init__(self, session)
		self["title"] = Label(_("Image Manager"))
		self['lab1'] = Label()
		self.emlist = []
		self.populate_List()
		self['list'] = MenuList(self.emlist)
		self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
			{
				'cancel': self.close,
				'red': self.close,
				'green': self.keyBackup,
				'yellow': self.keyResstore,
				'blue': self.keyDelete,
			}, -1)

		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("New Backup"))
		self["key_yellow"] = Button(_("Restore"))
		self["key_blue"] = Button(_("Delete"))

		self["MenuActions"] = HelpableActionMap(self, "MenuActions",
			{
				"menu": (self.createSetup, _("Open Context Menu"))
			}
		)


	def populate_List(self):
		global boxtype
		global BACKUP_DIRECTORY
		if not path.exists(config.plugins.VIXSettings.backuplocation.value):
			BACKUP_DIRECTORY = '/media/hdd/imagebackups'
			self['lab1'].setText(_("Device: /media/hdd") + _("\nSelect an image to Restore / Delete:"))
			self.session.open(MessageBox, _("The chosen location does not exist, using /media/hdd"), MessageBox.TYPE_INFO, timeout = 10)
		else:
			BACKUP_DIRECTORY = config.plugins.VIXSettings.backuplocation.value + '/imagebackups'
			self['lab1'].setText(_("Device: ") + config.plugins.VIXSettings.backuplocation.value + _("\nSelect an image to Restore / Delete:"))
		try:
			file = open('/etc/image-version', 'r')
			lines = file.readlines()
			file.close()
			for x in lines:
				splitted = x.split('=')
				if splitted[0] == "box_type":
					boxtype = splitted[1].replace('\n','') # 0 = release, 1 = experimental
		except:
			boxtype="not detected"

		if not path.exists(BACKUP_DIRECTORY):
			mkdir(BACKUP_DIRECTORY, 0755)
		if path.exists(BACKUP_DIRECTORY + '/turnoff_power'):
			remove(BACKUP_DIRECTORY + '/turnoff_power')
		images = listdir(BACKUP_DIRECTORY)
		del self.emlist[:]
		for fil in images:
			self.emlist.append(fil)
		self.emlist.sort()	

	def keyBackup(self):
		if boxtype == "vusolo" or boxtype == "vuduo" or boxtype == "et9000" or boxtype == "et5000":
			message = _("Are you ready to create a backup image ?")
			ybox = self.session.openWithCallback(self.BackupMemCheck, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Backup Confirmation"))
		else:
			self.session.open(MessageBox, _("Sorry you box is not yet compatible."), MessageBox.TYPE_INFO, timeout = 10)

	def keyResstore(self):
		if boxtype == "vusolo" or boxtype == "vuduo":
			self.sel = self['list'].getCurrent()
			if self.sel:
				message = _("Are you sure you want to restore this image:\n ") + self.sel
				ybox = self.session.openWithCallback(self.doResstore, MessageBox, message, MessageBox.TYPE_YESNO)
				ybox.setTitle(_("Restore Confirmation"))
			else:
				self.session.open(MessageBox, _("You have no image to restore."), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.session.open(MessageBox, _("Sorry you box is not yet compatible."), MessageBox.TYPE_INFO, timeout = 10)

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
			try:
				memcheck_stdout = popen('free | grep Total | tr -s " " | cut -d " " -f 4', "r")
				memcheck = memcheck_stdout.read()
				if int(memcheck) < 61440:
					mycmd1 = "echo '************************************************************************'"
					mycmd2 = "echo 'Creating swapfile'"
					mycmd3 = "dd if=/dev/zero of=" + BACKUP_DIRECTORY + "/swapfile_backup bs=1024 count=61440"
					mycmd4 = "mkswap " + BACKUP_DIRECTORY + "/swapfile_backup"
					mycmd5 = "swapon " + BACKUP_DIRECTORY + "/swapfile_backup"
					mycmd6 = "echo '************************************************************************'"
					self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doBackup,closeOnSuccess = True)
				else:
					self.doBackup()
			except:
				mycmd1 = "echo '************************************************************************'"
				mycmd2 = "echo 'Creating swapfile'"
				mycmd3 = "dd if=/dev/zero of=" + BACKUP_DIRECTORY + "/swapfile_backup bs=1024 count=61440"
				mycmd4 = "mkswap " + BACKUP_DIRECTORY + "/swapfile_backup"
				mycmd5 = "swapon " + BACKUP_DIRECTORY + "/swapfile_backup"
				mycmd6 = "echo '************************************************************************'"
				self.session.open(Console, title=_("Creating Image..."), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6], finishedCallback=self.doBackup,closeOnSuccess = True)
	
	def doBackup(self):
		global DATE
		global IMAGEVERSION
		global BUILDIMAGE
		global BACKUPIMAGE
		DATE_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		DATEtmp = DATE_stdout.read()
		DATE = DATEtmp.rstrip('\n')
		IMAGEVERSION_stdout = popen('date +%Y%m%d_%H%M%S', "r")
		IMAGEVERSIONtmp = IMAGEVERSION_stdout.read()
		IMAGEVERSION = DATEtmp.rstrip('\n')
#		OPTIONS=' --eraseblock=0x20000 -n -l'
		MKFS='/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/mkfs.jffs2'
		BUILDIMAGE='/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/buildimage'
		NANDDUMP='/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/nanddump'

		if boxtype == "vusolo" or boxtype == "vuduo":
			BACKUPIMAGE=BACKUP_DIRECTORY + '/' + DATE + '/vuplus-' + DATE + '.nfi'
			if path.exists(BACKUP_DIRECTORY + '/bi'):
				rmtree(BACKUP_DIRECTORY + '/bi')
			mkdir(BACKUP_DIRECTORY + '/bi', 0777)
			mkdir('/tmp/bi', 0777)
			mkdir('/tmp/bi/root', 0777)
			mkdir('/tmp/bi/boot', 0777)
			if path.exists(BACKUP_DIRECTORY + '/' + DATE + '/vuplus'):
				rmtree(BACKUP_DIRECTORY + '/' + DATE + '/vuplus')
			mkdir(BACKUP_DIRECTORY + '/' + DATE, 0777)
			mkdir(BACKUP_DIRECTORY + '/' + DATE + '/vuplus', 0777)
			mkdir(BACKUP_DIRECTORY + '/' + DATE + '/vuplus/' + boxtype, 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock0 /tmp/bi/root"
			mycmd5 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + BACKUP_DIRECTORY + '/bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating system root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + BACKUP_DIRECTORY + '/bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + BACKUP_DIRECTORY + '/bi/vmlinux.gz'
			mycmd12 = "echo '************************************************************************'"
			mycmd13 = "echo 'Creating Vu+ " + boxtype +  " Backup Images'"
			mycmd14 = "echo '************************************************************************'"
			mycmd15 = BUILDIMAGE + ' ' + BACKUP_DIRECTORY + '/bi/root.jffs2 ' + BACKUP_DIRECTORY + '/bi/boot.jffs2 ' + BACKUP_DIRECTORY + '/bi/vmlinux.gz > ' + BACKUPIMAGE
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15], finishedCallback=self.doBackup2,closeOnSuccess = True)

		elif boxtype == "et9000" or boxtype == "et5000":
			if path.exists(BACKUP_DIRECTORY + '/bi'):
				rmtree(BACKUP_DIRECTORY + '/bi')
			mkdir(BACKUP_DIRECTORY + '/bi', 0777)
			mkdir('/tmp/bi', 0777)
			mkdir('/tmp/bi/root', 0777)
			mkdir('/tmp/bi/boot', 0777)
			if path.exists(BACKUP_DIRECTORY + '/' + DATE):
				rmtree(BACKUP_DIRECTORY + '/' + DATE)
			mkdir(BACKUP_DIRECTORY + '/' + DATE, 0777)
			mkdir(BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype, 0777)

			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Clarke-Tech " + boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "mount -t jffs2 /dev/mtdblock2 /tmp/bi/boot"
			mycmd5 = "mount -t jffs2 /dev/mtdblock3 /tmp/bi/root"
			mycmd6 = "echo 'Creating Boot sector'"
			mycmd7 = MKFS + ' --root=/tmp/bi/boot --faketime --output=' + BACKUP_DIRECTORY + '/bi/boot.jffs2 --eraseblock=0x20000 -n -l'
			mycmd8 = "echo 'Creating system root, this will take some time to complete, please wait...'"
			mycmd9 = MKFS + ' --root=/tmp/bi/root --faketime --output=' + BACKUP_DIRECTORY + '/bi/root.jffs2 --eraseblock=0x20000 -n -l'
			mycmd10 = "echo 'Creating kernel structure'"
			mycmd11 = NANDDUMP + ' /dev/mtd1 -o -b > ' + BACKUP_DIRECTORY + '/bi/vmlinux.gz'
			mycmd12 = "echo '************************************************************************'"
			mycmd13 = "echo 'Creating Clarke-Tech " + boxtype +  " Backup Images'"
			mycmd14 = "echo '************************************************************************'"
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14], finishedCallback=self.doBackup2,closeOnSuccess = True)

	def doBackup2(self):
		if boxtype == "vusolo" or boxtype == "vuduo":
			move(BACKUP_DIRECTORY + '/bi/root.jffs2', BACKUP_DIRECTORY + '/' + DATE + '/vuplus/' + boxtype +'/root_cfe_auto.jffs2')
			move(BACKUP_DIRECTORY + '/bi/boot.jffs2', BACKUP_DIRECTORY + '/' + DATE + '/vuplus/' + boxtype +'/boot_cfe_auto.jffs2')
			move(BACKUP_DIRECTORY + '/bi/vmlinux.gz', BACKUP_DIRECTORY + '/' + DATE + '/vuplus/' + boxtype +'/kernel_cfe_auto.bin')
			system('umount /tmp/bi/root')
			system('umount /tmp/bi/boot')
			rmtree('/tmp/bi')
			rmtree(BACKUP_DIRECTORY + '/bi')
			if path.exists(BACKUP_DIRECTORY + '/swapfile_backup'):
				system('swapoff ' + BACKUP_DIRECTORY + '/swapfile_backup')
				remove(BACKUP_DIRECTORY + '/swapfile_backup')
			if path.exists(BACKUPIMAGE) and path.exists(BACKUP_DIRECTORY + '/' + DATE + '/vuplus/' + boxtype):
				self.session.open(MessageBox, _("NFI & USB Images created in " + BACKUP_DIRECTORY + '/' + DATE), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Image creation failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
		elif boxtype == "et9000" or boxtype == "et5000":
			move(BACKUP_DIRECTORY + '/bi/root.jffs2', BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype +'/rootfs.bin')
			move(BACKUP_DIRECTORY + '/bi/boot.jffs2', BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype +'/boot.bin')
			move(BACKUP_DIRECTORY + '/bi/vmlinux.gz', BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype +'/kernel.bin')
			fileout = open(BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype + '/noforce', 'w')
			line = "rename this file to 'force' to force an update without confirmation"
			fileout.write(line)
			fileout.close()
			fileout = open(BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype + '/imageversion', 'w')
			line = "ViX-" + IMAGEVERSION
			fileout.write(line)
			fileout.close()
			system('umount /tmp/bi/root')
			system('umount /tmp/bi/boot')
			rmtree('/tmp/bi')
			rmtree(BACKUP_DIRECTORY + '/bi')
			if path.exists(BACKUP_DIRECTORY + '/swapfile_backup'):
				system('swapoff ' + BACKUP_DIRECTORY + '/swapfile_backup')
				remove(BACKUP_DIRECTORY + '/swapfile_backup')
			if fileExists(BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype +'/rootfs.bin') and fileExists(BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype +'/boot.bin') and fileExists(BACKUP_DIRECTORY + '/' + DATE + '/' + boxtype +'/kernel.bin'):
				self.session.open(MessageBox, _("USB Image created in " + BACKUP_DIRECTORY + '/' + DATE), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Image creation failed - e. g. wrong backup destination or no space left on backup device"), MessageBox.TYPE_INFO, timeout = 10)
		self.populate_List()

	def doResstore(self, answer):
		NANDWRITE='/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/nandwrite'
		if answer is True:
			selectedimage = self.sel
			if not path.exists(BACKUP_DIRECTORY + '/turnoff_power'):
				copy('/usr/bin/turnoff_power', BACKUP_DIRECTORY + '/')
			mycmd1 = "echo '************************************************************************'"
			mycmd2 = "echo 'Vu+ " + boxtype +  " detected'"
			mycmd3 = "echo '************************************************************************'"
			mycmd4 = "echo ' '"
			mycmd5 = "echo 'Attention:'"
			mycmd6 = "echo ' '"
			mycmd7 = "echo 'Your Vuplus will be powered off automatically after the flashing progress.'"
			mycmd8 = "echo 'Please power on again after 60 seconds to boot the flashed image.'"
			mycmd9 = "echo ' '"
			mycmd10 = "echo 'Preparing Flashprogress.'"
			mycmd11 = "echo 'Erasing NAND Flash.'"
			mycmd12 = 'flash_eraseall --j /dev/mtd2'
			mycmd13 = 'flash_eraseall --j /dev/mtd1'
			mycmd14 = "echo ' '"
			mycmd15 = "echo 'Flasing Image to NAND.'"
			mycmd16 = "echo ' '"
			mycmd17 = NANDWRITE + ' -p /dev/mtd2 ' + BACKUP_DIRECTORY + '/' + selectedimage + '/vuplus/' + boxtype + '/boot_cfe_auto.jffs2'
			mycmd18 = NANDWRITE + ' -p /dev/mtd1 ' + BACKUP_DIRECTORY + '/' + selectedimage + '/vuplus/' + boxtype + '/kernel_cfe_auto.bin'
			mycmd19 = 'flash_eraseall -j /dev/mtd0'
			mycmd20 = NANDWRITE + ' -p /dev/mtd0 ' + BACKUP_DIRECTORY + '/' + selectedimage + '/vuplus/' + boxtype + '/root_cfe_auto.jffs2'
			mycmd21 = "echo 'Flasing Complete.'"
			mycmd22 = BACKUP_DIRECTORY + '/turnoff_power'
			self.session.open(Console, title='Creating Image...', cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6, mycmd7, mycmd8, mycmd9, mycmd10, mycmd11, mycmd12, mycmd13, mycmd14, mycmd15, mycmd16, mycmd17, mycmd18, mycmd19, mycmd20, mycmd21, mycmd22],closeOnSuccess = True)

	def doDelete(self, answer):
		if answer is True:
			self.sel = self['list'].getCurrent()
			selectedimage = self.sel
			rmtree(BACKUP_DIRECTORY + '/' + selectedimage)
		self.populate_List()

	def myclose(self):
		self.close()
		
	def createSetup(self):
		self["title"] = Label(_("Image Manager"))
		parts = []
		for p in harddiskmanager.getMountedPartitions():
			d = path.normpath(p.mountpoint)
			print 'd test',d
			print 'p test',p
			if path.exists(p.mountpoint) and p.mountpoint != "/" and (p.mountpoint != ''):
				parts.append((p.description, d))
		if len(parts):
			self.session.openWithCallback(self.backuplocation_choosen, ChoiceBox, title = _("Please select medium to use as backup location"), list = parts)

	def backuplocation_choosen(self, option):
		if option is not None:
			config.plugins.VIXSettings.backuplocation.value = str(option[1])
		config.plugins.VIXSettings.backuplocation.save()
		config.plugins.VIXSettings.save()
		config.save()
		self.populate_List()
