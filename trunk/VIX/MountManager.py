from Screens.Screen import Screen
from enigma import eTimer
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.PluginComponent import plugins
from Components.ConfigList import ConfigListScreen
from Components.config import getConfigListEntry, config, ConfigYesNo, ConfigText, ConfigSelection, ConfigClock, NoSave, configfile
from Components.Sources.List import List
from Components.Console import Console
from Components.Language import language
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists, pathExists, createDir, resolveFilename, SCOPE_LANGUAGE, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from Plugins.Plugin import PluginDescriptor
from enigma import eTimer
from Screens.VirtualKeyBoard import VirtualKeyBoard
from os import system, rename, path, mkdir, remove, statvfs, environ, listdir
import time, datetime, gettext

lang = language.getLanguage()
environ["LANGUAGE"] = lang[:2]
print "[MounManager] set language to ", lang[:2]
gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
gettext.textdomain("enigma2")
gettext.bindtextdomain("MounManager", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "SystemPlugins/ViX/locale"))

def _(txt):
	t = gettext.dgettext("MounManager", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t

class VIXDevicesPanel(Screen):
	skin = """
	<screen position="center,center" size="640,460" title="Mount Manager">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="325,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="475,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="key_yellow" position="325,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="key_blue" position="475,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" />
		<widget source="list" render="Listbox" position="10,50" size="620,450" scrollbarMode="showOnDemand" >
			<convert type="TemplatedMultiContent">
				{"template": [
				 MultiContentEntryText(pos = (90, 0), size = (600, 30), font=0, text = 0),
				 MultiContentEntryText(pos = (110, 30), size = (600, 50), font=1, flags = RT_VALIGN_TOP, text = 1),
				 MultiContentEntryPixmapAlphaBlend(pos = (0, 0), size = (80, 80), png = 2),
				],
				"fonts": [gFont("Regular", 24),gFont("Regular", 20)],
				"itemHeight": 85
				}
			</convert>
		</widget>
		<widget name="lab1" zPosition="2" position="50,90" size="600,40" font="Regular;22" halign="center" transparent="1"/>
	</screen>"""
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Mount Manager"))
		self['key_red'] = Label(" ")
		self['key_green'] = Label(_('Setup Mounts'))
		self['key_yellow'] = Label(_(' '))
		self['key_blue'] = Label(_(' '))
		self['lab1'] = Label()
		self.list = []
		self['list'] = List(self.list)
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'back': self.close, 'green': self.SetupMounts, 'red': self.saveMypoints})
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updateList2)
		self.Console = Console()
		self.updateList()

	def selectionChanged(self):
		if len(self.list) == 0:
			return
		self.sel = self['list'].getCurrent()
		seldev = self.sel
		for line in self.sel:
			try:
				line = line.strip()
				if line.find('Mount') >= 0:
					if line.find('/media/hdd') < 0:
						self["key_red"].setText(_("Use as HDD"))
				else:
					self["key_red"].setText(_(" "))
			except:
				pass

	def updateList(self):
		scanning = _("Wait please while scanning for devices...")
		self['lab1'].setText(scanning)
		self.activityTimer.start(10)

	def updateList2(self):
		self.activityTimer.stop()
		self.list = []
		list2 = []
		if path.exists('/tmp/devices.tmp'):
			remove('/tmp/devices.tmp')
		if not self.Console:
			self.Console = Console()
		self.Console.ePopen('fdisk -l /dev/sd? | grep /dev/sd | grep -v bytes >/tmp/devices.tmp')
		time.sleep(1)
		file('/tmp/devices.tmp1', 'w').writelines([l for l in file('/tmp/devices.tmp').readlines() if 'swap' not in l])
		rename('/tmp/devices.tmp1','/tmp/devices.tmp')
		f = open('/tmp/devices.tmp', 'r')
		for line in f.readlines():
			parts = line.strip().split()
			device = parts[0]
			device = device.strip().replace('/dev/', '')
			if device in list2:
				continue
			self.buildMy_rec(device)
			list2.append(device)
		f.close()
		self['list'].list = self.list
		self['lab1'].hide()

	def buildMy_rec(self, device):
		try:
			if device.find('1') > 0:
				device2 = device.replace('1', '')
		except:
			device2 = ''
		try:
			if device.find('2') > 0:
				device2 = device.replace('2', '')
		except:
			device2 = ''
		try:
			if device.find('3') > 0:
				device2 = device.replace('3', '')
		except:
			device2 = ''
		try:
			if device.find('4') > 0:
				device2 = device.replace('4', '')
		except:
			device2 = ''
		devicetype = path.realpath('/sys/block/' + device2 + '/device')
		d2 = device
		name = 'USB: '
		mypixmap = '/usr/share/enigma2/ViX_HD/icons/dev_usb.png'
		model = file('/sys/block/' + device2 + '/device/model').read()
		model = str(model).replace('\n', '')
		des = ''
		if devicetype.find('/devices/pci') != -1:
			name = _("HARD DISK: ")
			mypixmap = '/usr/share/enigma2/ViX_HD/icons/dev_hdd.png'
		name = name + model
		f = open('/proc/mounts', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				d1 = parts[1]
				rw = parts[3]
				break
				continue
			else:
				d1 = _("None")
				rw = _("None")
		f.close()
		f = open('/proc/partitions', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				size = int(parts[2])
				if ((size / 1024) / 1024) > 1:
					des = _("Size: ") + str((size / 1024) / 1024) + _("GB")
				else:
					des = _("Size: ") + str(size / 1024) + _("MB")
			else:
				try:
					size = file('/sys/block/' + device2 + '/' + device + '/size').read()
					size = str(size).replace('\n', '')
					size = int(size)
				except:
					size = 0
				if (((size / 2) / 1024) / 1024) > 1:
					des = _("Size: ") + str(((size / 2) / 1024) / 1024) + _("GB")
				else:
					des = _("Size: ") + str((size / 2) / 1024) + _("MB")
		f.close()
		f = open('/tmp/devices.tmp', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				try:
					dtype = parts[5] + ' ' + parts[6]
				except:
					dtype = parts[5]
				break
				continue
		f.close()
		if des != '':
			if rw.startswith('rw'):
				rw = ' R/W'
			elif rw.startswith('ro'):
				rw = ' R/O'
			else:
				rw = ""			
			des += '\t' + _("Mount: ") + d1 + '\n' + _("Device: ") + '/dev/' + device + '\t' + _("Type: ") + dtype + rw
			png = LoadPixmap(mypixmap)
			res = (name, des, png)
			self.list.append(res)

	def mountUmount(self):
		self.session.openWithCallback(self.updateList, VIXDevicePanelConf)

	def Partition(self):
		self.session.openWithCallback(self.updateList, VIXPartitionPanelConf)

	def SetupMounts(self):
		self.session.openWithCallback(self.updateList, VIXDevicePanelConf)

	def Format(self):
		sel = self['list'].getCurrent()
		if sel:
			sel
			messinfo = ''
			name = sel[0]
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			mountp = parts[1].replace(_("Mount: "), '')
			device = parts[2].replace(_("Device: "), '')
			self.nformat = name
			self.mformat = mountp
			self.dformat = device
			mess = _("Warning you are going to format ") + name + _("\nALL THE DATA ON THIS PARTITION WILL BE LOST!\n Are you sure to continue?")
			self.session.openWithCallback(self.Unmount, MessageBox, mess, MessageBox.TYPE_YESNO)
		else:
			sel

	def Unmount(self, answer):
		if answer is True:
			target = self.mformat
			device = self.dformat
			system ('umount ' + device)
			try:
				mounts = open("/proc/mounts")
			except IOError:
				return -1
			mountcheck = mounts.readlines()
			mounts.close()
			for line in mountcheck:
				parts = line.strip().split(" ")
				if path.realpath(parts[0]).startswith(device):
					ok = "Flase"
					self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths"), MessageBox.TYPE_INFO)
				else:
					ok = ""

			if ok != "False":
				system ('mkfs.ext3 -T largefile -m0 -O dir_index ' + device)
				self.session.openWithCallback(self.hreBoot, MessageBox, _("The device in now formatted.\nPress ok to continue"), MessageBox.TYPE_INFO)

	def hreBoot(self, answer):
		system('mount -a')
		self.updateList()

	def saveMypoints(self):
		sel = self['list'].getCurrent()
		if sel:
			for x in self['list'].list:
				try:
					x = x[1].strip()
					print 'x',x
					if x.find('Mount') >= 0:
						parts = x.split()
						device = parts[5]
						print 'parts',parts
						print 'device',device
						file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if device not in l])
						rename('/etc/fstab.tmp','/etc/fstab')
				except:
					pass
			for line in self.sel:
				try:
					line = line.strip()
					if line.find('Mount') >= 0:
						if line.find('/media/hdd') < 0:
							parts = line.split()
							device = parts[5]
							print 'parts',parts
							print 'device',device
							device = device.replace('/autofs/', '/dev/')
							out = open('/etc/fstab', 'a')
							line = device + '            /media/hdd           auto       defaults              0 0\n'
							out.write(line)
							out.close()
							message = _("Devices changes need a system restart to take effects.\nRestart your Box now?")
							ybox = self.session.openWithCallback(self.restBo, MessageBox, message, MessageBox.TYPE_YESNO)
							ybox.setTitle(_("Restart box."))
						else:
							self.session.open(MessageBox, _("This Device is already mounted as HDD."), MessageBox.TYPE_INFO, timeout = 10, close_on_any_key = True)
				except:
					pass
			
	def restBo(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.updateList()
			self.selectionChanged()

class VIXDevicePanelConf(Screen, ConfigListScreen):
	skin = """
	<screen position="center,center" size="640,460" title="Choose where to mount your devices to:">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="config" position="30,60" size="580,275" scrollbarMode="showOnDemand"/>
		<widget name="Linconn" position="30,375" size="580,20" font="Regular;18" halign="center" valign="center" backgroundColor="#9f1313"/>
	</screen>"""
	def __init__(self, session):
		Screen.__init__(self, session)
		self.list = []
		ConfigListScreen.__init__(self, self.list)
		Screen.setTitle(self, _("Choose where to mount your devices to:"))
		self['key_green'] = Label(_('Save'))
		self['key_red'] = Label(_('Cancel'))
		self['Linconn'] = Label(_("Wait please while scanning your box devices..."))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'green': self.saveMypoints, 'red': self.close, 'back': self.close})
		self.Console = Console()
		self.updateList()

	def updateList(self):
		self.list = []
		list2 = []
		f = open('/tmp/devices.tmp', 'r')
		for line in f.readlines():
			parts = line.strip().split()
			device = parts[0]
			device = device.strip().replace('/dev/', '')
			if device in list2:
				continue
			self.buildMy_rec(device)
			list2.append(device)
		f.close()
		self['config'].list = self.list
		self['config'].l.setList(self.list)
		self['Linconn'].hide()

	def buildMy_rec(self, device):
		try:
			if device.find('1') > 0:
				device2 = device.replace('1', '')
		except:
			device2 = ''
		try:
			if device.find('2') > 0:
				device2 = device.replace('2', '')
		except:
			device2 = ''
		try:
			if device.find('3') > 0:
				device2 = device.replace('3', '')
		except:
			device2 = ''
		try:
			if device.find('4') > 0:
				device2 = device.replace('4', '')
		except:
			device2 = ''
		devicetype = path.realpath('/sys/block/' + device2 + '/device')
		d2 = device
		name = 'USB: '
		mypixmap = '/usr/share/enigma2/ViX_HD/icons/dev_usb.png'
		model = file('/sys/block/' + device2 + '/device/model').read()
		model = str(model).replace('\n', '')
		des = ''
		if devicetype.find('/devices/pci') != -1:
			name = _("HARD DISK: ")
			mypixmap = '/usr/share/enigma2/ViX_HD/icons/dev_hdd.png'
		name = name + model
		f = open('/proc/mounts', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				d1 = parts[1]
				break
				continue
			else:
				d1 = _("None")
		f.close()
		f = open('/proc/partitions', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				size = int(parts[2])
				if ((size / 1024) / 1024) > 1:
					des = _("Size: ") + str((size / 1024) / 1024) + _("GB")
				else:
					des = _("Size: ") + str(size / 1024) + _("MB")
			else:
				try:
					size = file('/sys/block/' + device2 + '/' + device + '/size').read()
					size = str(size).replace('\n', '')
					size = int(size)
				except:
					size = 0
				if (((size / 2) / 1024) / 1024) > 1:
					des = _("Size: ") + str(((size / 2) / 1024) / 1024) + _("GB")
				else:
					des = _("Size: ") + str((size / 2) / 1024) + _("MB")
		f.close()
		f = open('/tmp/devices.tmp', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				try:
					dtype = parts[5] + ' ' + parts[6]
				except:
					dtype = parts[5]
				break
				continue
		f.close()
		item = NoSave(ConfigSelection(default='/media/' + device, choices=[('/media/' + device, '/media/' + device),
		('/media/hdd', '/media/hdd'),
		('/media/hdd2', '/media/hdd2'),
		('/media/hdd3', '/media/hdd3'),
		('/media/usb', '/media/usb'),
		('/media/usb2', '/media/usb2'),
		('/media/usb3', '/media/usb3')]))
		if (d1 == '/media/meoboot'):
			item = NoSave(ConfigSelection(default='/media/meoboot', choices=[('/media/meoboot', '/media/meoboot')]))
		if dtype == 'Linux':
			dtype = 'ext3'
		else:
			dtype = 'auto'
		item.value = d1.strip()
		text = name + ' ' + des + ' /dev/' + device
		res = getConfigListEntry(text, item, device, dtype)

		if des != '' and self.list.append(res):
			pass

	def saveMypoints(self):
		mycheck = False
		for x in self['config'].list:
			device = x[2]
			mountp = x[1].value
			type = x[3]
			file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if device not in l])
			rename('/etc/fstab.tmp','/etc/fstab')

		for x in self['config'].list:
			device = x[2]
			mountp = x[1].value
			if not path.exists(mountp):
				mkdir(mountp, 0755)
			if mountp == '/media/meoboot':
				continue
			out = open('/etc/fstab', 'a')
			line = '/dev/' + device + '            ' + mountp + '           ' + type + '       defaults              0 0\n'
			out.write(line)
			out.close()
		if mycheck == True:
			nobox = self.session.open(MessageBox, _("Error: You have to set Mountpoins for all your devices."), MessageBox.TYPE_INFO)
			nobox.setTitle(_('Error'))
		else:
			message = _("Devices changes need a system restart to take effects.\nRestart your Box now?")
			ybox = self.session.openWithCallback(self.restBo, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Restart box."))
			
	def restBo(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.close()

class VIXPartitionPanelConf(Screen, ConfigListScreen):
	skin = """
	<screen position="center,center" size="640,460" title="Devices Manager">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget source="list" render="Listbox" position="10,50" size="620,450" scrollbarMode="showOnDemand" >
			<convert type="TemplatedMultiContent">
				{"template": [
				 MultiContentEntryText(pos = (90, 0), size = (600, 30), font=0, text = 0),
				 MultiContentEntryText(pos = (110, 30), size = (600, 50), font=1, flags = RT_VALIGN_TOP, text = 1),
				 MultiContentEntryPixmapAlphaBlend(pos = (0, 0), size = (80, 80), png = 2),
				],
				"fonts": [gFont("Regular", 24),gFont("Regular", 20)],
				"itemHeight": 85
				}
			</convert>
		</widget>
		<widget name="lab1" zPosition="2" position="50,90" size="600,40" font="Regular;22" halign="center" transparent="1"/>
'	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Repartition Device"))
		self['key_green'] = Label(_('Format'))
		self['key_red'] = Label(_('Cancel'))
		self['lab1'] = Label()
		self.list = []
		self['list'] = List(self.list)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'green': self.myFormat, 'red': self.close, 'back': self.close})
		self.Console = Console()
		self.updateList()

	def updateList(self):
		self.list = []
		list2 = []
		f = open('/tmp/devices.tmp', 'r')
		for line in f.readlines():
			parts = line.strip().split()
			device = parts[0]
			device = device.strip().replace('/dev/', '')
			if device in list2:
				continue
			self.buildMy_rec(device)
			list2.append(device)
		f.close()
		self['list'].list = self.list
		self['lab1'].hide()

	def buildMy_rec(self, device):
		device2 = device.replace('1', '')
		devicetype = path.realpath('/sys/block/' + device2 + '/device')
		d2 = device
		name = 'USB: '
		mypixmap = '/usr/share/enigma2/ViX_HD/icons/dev_usb.png'
		model = file('/sys/block/' + device2 + '/device/model').read()
		model = str(model).replace('\n', '')
		des = ''
		if devicetype.find('/devices/pci') != -1:
			name = _("HARD DISK: ")
			mypixmap = '/usr/share/enigma2/ViX_HD/icons/dev_hdd.png'
		name = name + model
		f = open('/proc/partitions', 'r')
		for line in f.readlines():
			if line.find(device2) != -1:
				parts = line.strip().split()
				size = int(parts[2])
				if ((size / 1024) / 1024) > 1:
					des = _("Size: ") + str((size / 1024) / 1024) + _("GB")
				else:
					des = _("Size: ") + str(size / 1024) + _("MB")
			else:
				try:
					size = file('/sys/block/' + device2 + '/' + device + '/size').read()
					size = str(size).replace('\n', '')
					size = int(size)
				except:
					size = 0
				if (((size / 2) / 1024) / 1024) > 1:
					des = _("Size: ") + str(((size / 2) / 1024) / 1024) + _("GB")
				else:
					des = _("Size: ") + str((size / 2) / 1024) + _("MB")
		f.close()
		f = open('/tmp/devices.tmp', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				try:
					dtype = parts[5] + ' ' + parts[6]
				except:
					dtype = parts[5]
				break
				continue
		f.close()
		if des != '':
			if rw.startswith('rw'):
				rw = ' R/W'
			elif rw.startswith('ro'):
				rw = ' R/O'
			else:
				rw = ""			
			des += '\t' + _("Mount: ") + d1 + '\n' + _("Device: ") + '/dev/' + device + '\t' + _("Type: ") + dtype + rw
			png = LoadPixmap(mypixmap)
			res = (name, des, png)
			self.list.append(res)

	def myFormat(self):
		sel = self['list'].getCurrent()
		if sel:
			sel
			messinfo = ''
			name = sel[0]
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			print 'part',parts
			device2 = parts[1].replace(_("Device: "), '')
			device = device2.replace('1', '')
			self.nformat = name
			self.dformat = device
			mess = _("Warning you are going to format\n") + name + _("\nALL THE DATA WILL BE LOST!\nAre you sure to continue?")
			self.session.openWithCallback(self.Unmount, MessageBox, mess, MessageBox.TYPE_YESNO)
		else:
			sel

	def Unmount(self, answer):
		if answer is True:
			device = self.dformat
			system ('umount ' + device + '1')
			try:
				mounts = open("/proc/mounts")
			except IOError:
				return -1
			mountcheck = mounts.readlines()
			mounts.close()
			for line in mountcheck:
				parts = line.strip().split(" ")
				if path.realpath(parts[0]).startswith(device + '1'):
					ok = "Flase"
					self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths"), MessageBox.TYPE_INFO)
				else:
					system ('umount ' + device + '2')
					try:
						mounts = open("/proc/mounts")
					except IOError:
						return -1
					mountcheck = mounts.readlines()
					mounts.close()
					if path.realpath(parts[0]).startswith(device + '2'):
						ok = "Flase"
						self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths"), MessageBox.TYPE_INFO)
					else:
						system ('umount ' + device + '3')
						try:
							mounts = open("/proc/mounts")
						except IOError:
							return -1
						mountcheck = mounts.readlines()
						mounts.close()
						if path.realpath(parts[0]).startswith(device + '3'):
							ok = "Flase"
							self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths"), MessageBox.TYPE_INFO)
						else:
							system ('umount ' + device + '4')
							try:
								mounts = open("/proc/mounts")
							except IOError:
								return -1
							mountcheck = mounts.readlines()
							mounts.close()
							if path.realpath(parts[0]).startswith(device + '4'):
								self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths"), MessageBox.TYPE_INFO)
							else:
								ok = ""
			if ok != "False":
				system ('printf "d\n4\nd\n3\nd\n2\nd\nn\np\n1\n\n\nw\n" | fdisk ' + device)
				time.sleep(2)
				system ('umount ' + device + '1')
				time.sleep(2)
				system ('mkfs.ext3 -T largefile -m0 -O dir_index ' + device + '1')
				self.session.openWithCallback(self.hreBoot, MessageBox, _("The device in now formatted to ext3\nPress ok to continue"), MessageBox.TYPE_INFO)

	def hreBoot(self, answer):
		system('mount -a')
		self.close()