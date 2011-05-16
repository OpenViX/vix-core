from Components.Button import Button
from Components.ActionMap import ActionMap, NumberActionMap
from Components.config import getConfigListEntry, config, ConfigSubsection, ConfigYesNo, ConfigText, ConfigSelection, ConfigInteger, ConfigClock, NoSave, configfile
from Components.ConfigList import ConfigListScreen, ConfigList
from Components.Label import Label
from Components.Sources.List import List
from Components.ScrollLabel import ScrollLabel
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Harddisk import harddiskmanager
from Components.Language import language
from Components.Pixmap import Pixmap,MultiPixmap
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Console import Console
from Tools.Directories import resolveFilename, SCOPE_LANGUAGE, SCOPE_PLUGINS
from Tools.LoadPixmap import LoadPixmap
from base64 import encodestring
from enigma import eListboxPythonMultiContent, ePoint, eTimer, getDesktop, gFont, iPlayableService, iServiceInformation, loadPNG, RT_HALIGN_RIGHT
from skin import parseColor
from os import system, environ, listdir, remove, rename, symlink, unlink, path, mkdir, access, W_OK, R_OK, F_OK
import gettext
from enigma import eTimer, ePoint

lang = language.getLanguage()
environ["LANGUAGE"] = lang[:2]
print "[CronManager] set language to ", lang[:2]
gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
gettext.textdomain("enigma2")
gettext.bindtextdomain("CronManager", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "SystemPlugins/ViX/locale"))

choiceslist = [('None', 'None')]
config.plugins.vixcron  = ConfigSubsection()
config.plugins.vixcron.default_command = NoSave(ConfigSelection(default='None', choices = choiceslist))
config.plugins.vixcron.cmdtime = NoSave(ConfigClock(default=0))
config.plugins.vixcron.cmdtime.value, mytmpt = ([0, 0], [0, 0])
config.plugins.vixcron.user_command = NoSave(ConfigText(default='None', fixed_size=False))
config.plugins.vixcron.runwhen = NoSave(ConfigSelection(default='Daily', choices = [('Hourly', 'Hourly'),('Daily', 'Daily'),('Weekly', 'Weekly'),('Monthly', 'Monthly')]))
config.plugins.vixcron.dayofweek = NoSave(ConfigSelection(default='Monday', choices = [('Monday', 'Monday'),('Tuesday', 'Tuesday'),('Wednesday', 'Wednesday'),('Thursday', 'Thursday'),('Friday', 'Friday'),('Saturday', 'Saturday'),('Sunday', 'Sunday')]))
config.plugins.vixcron.dayofmonth = NoSave(ConfigInteger(default=1, limits=(1, 31)))

def _(txt):
	t = gettext.dgettext("CronManager", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t

class VIXCronManager(Screen):
	skin = """
		<screen position="center,center" size="560,400" title="Cron Manager">
			<widget source="list" render="Listbox" position="10,10" size="540,360" scrollbarMode="showOnDemand" >
				<convert type="StringList" />
			</widget>
			<ePixmap pixmap="skin_default/buttons/red.png" position="90,350" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="330,350" size="140,40" alphatest="on" />
			<widget name="key_red" position="90,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_yellow" position="330,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		</screen>"""


	def __init__(self, session):
		Screen.__init__(self, session)
		if not path.exists('/usr/scripts'):
			mkdir('/usr/scripts', 0755)
		self["title"] = Label(_("Cron Manager"))
		self['key_red'] = Label(_('Add'))
		self['key_yellow'] = Label(_('Delete'))
		self.list = []
		self['list'] = List(self.list)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.addtocron, 'yellow': self.delcron})
		self.updateList()

	def addtocron(self):
		self.session.openWithCallback(self.updateList, VIXSetupCronConf)

	def updateList(self):
		self.list = []
		if path.exists('/etc/cron/crontabs/root'):
			f = open('/etc/cron/crontabs/root', 'r')
			for line in f.readlines():
				parts = line.strip().split()
				if parts[1] == '*':
					line2 = 'Hourly: \t\t' + 'Command: ' + parts[5]
				elif parts[2] == '*' and parts[4] == '*':
					line2 = 'Daily: ' + parts[1] + ':' + parts[0] + '\t\t' + 'Command: ' + parts[5]
				elif parts[3] == '*':
						if parts[4] == "*":
							line2 = 'Monthly:  Day ' + parts[2] + '  ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "0":
							line2 = 'Weekly:  Sunday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "1":
							line2 = 'Weekly:  Monday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "2":
							line2 = 'Weekly:  Tuesday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "3":
							line2 = 'Weekly:  Wednesday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "4":
							line2 = 'Weekly:  Thursday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "5":
							line2 = 'Weekly:  Friday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]
						elif parts[4] == "6":
							line2 = 'Weekly:  Saturday ' + parts[1] + ':' + parts[0] + '\t' + 'Command: ' + parts[5]

				res = (line2, line)
				self.list.append(res)
			f.close()
		self['list'].list = self.list

	def delcron(self):
		mysel = self['list'].getCurrent()
		if mysel:
			mysel
			myline = mysel[1]
			file('/etc/cron/crontabs/root.tmp', 'w').writelines([l for l in file('/etc/cron/crontabs/root').readlines() if myline not in l])
			rename('/etc/cron/crontabs/root.tmp','/etc/cron/crontabs/root')
			rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
			self.updateList()
		else:
			mysel

class VIXSetupCronConf(Screen, ConfigListScreen):
	skin = """
		<screen position="center,center" size="560,400" title="Cron Manager">
			<widget name="config" position="10,20" size="540,400" scrollbarMode="showOnDemand" />
			<ePixmap pixmap="skin_default/buttons/red.png" position="90,350" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="330,350" size="140,40" alphatest="on" />
			<widget name="key_red" position="90,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_yellow" position="330,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget name="HelpWindow" pixmap="skin_default/vkey_icon.png" position="160,260" zPosition="1" size="1,1" transparent="1" alphatest="on" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self["title"] = Label(_("Cron Manager"))
		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self['key_red'] = Label(_('Save'))
		self['key_yellow'] = Label(_('KeyBoard'))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'red': self.checkentry, 'back': self.close, 'yellow': self.vkeyb})
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self.createSetup()

	def createSetup(self):
		f = listdir('/usr/scripts')
		if f:
			for line in f:
				parts = line.split()
				path = "/usr/scripts/"
				pkg = parts[0]
				description = path + parts[0]
				if pkg.find('.sh') >= 0:
					choiceslist.append((description, pkg))
			choiceslist.sort()
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Run how often ?"), config.plugins.vixcron.runwhen))
		if config.plugins.vixcron.runwhen.value != 'Hourly':
			self.list.append(getConfigListEntry(_("Time to execute command or script"), config.plugins.vixcron.cmdtime))
		if config.plugins.vixcron.runwhen.value == 'Weekly':
			self.list.append(getConfigListEntry(_("What Day of week ?"), config.plugins.vixcron.dayofweek))
		if config.plugins.vixcron.runwhen.value == 'Monthly':
			self.list.append(getConfigListEntry(_("What Day of month ?"), config.plugins.vixcron.dayofmonth))
		self.list.append(getConfigListEntry(_('Predefined Command to execute'), config.plugins.vixcron.default_command))
		self.list.append(getConfigListEntry(_("Command To Run"), config.plugins.vixcron.user_command))
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

	def vkeyb(self):
		sel = self['config'].getCurrent()
		if sel:
			sel
			self.vkvar = sel[0]
			value = 'xmeo'
			if self.vkvar == _("Command To Run"):
				value = config.plugins.vixcron.user_command.value
				if value == _("None"):
					value = ''
			if value != 'xmeo':
				self.session.openWithCallback(self.UpdateAgain, VirtualKeyBoard, title=self.vkvar, text=value)
			else:
				self.session.open(MessageBox, _("Please use Virtual Keyboard for text rows only"), MessageBox.TYPE_INFO)
		else:
			sel

	def UpdateAgain(self, newt):
		self.list = []
		if newt is None or newt == '':
			newt = _("None")
		config.plugins.vixcron.user_command.value = newt
		self.list.append(getConfigListEntry(_("Run how often ?"), config.plugins.vixcron.runwhen))
		if config.plugins.vixcron.runwhen.value != 'Hourly':
			self.list.append(getConfigListEntry(_("Time to execute command or script"), config.plugins.vixcron.cmdtime))
		if config.plugins.vixcron.runwhen.value == 'Weekly':
			self.list.append(getConfigListEntry(_("What Day of week ?"), config.plugins.vixcron.dayofweek))
		if config.plugins.vixcron.runwhen.value == 'Monthly':
			self.list.append(getConfigListEntry(_("What Day of month ?"), config.plugins.vixcron.dayofmonth))
		self.list.append(getConfigListEntry(_('Predefined Command to execute'), config.plugins.vixcron.default_command))
		self.list.append(getConfigListEntry(_("Command To Run"), config.plugins.vixcron.user_command))
		self['config'].list = self.list
		self['config'].l.setList(self.list)
		return None

	def checkentry(self):
		msg = ''
		if config.plugins.vixcron.user_command.value == 'None':
			config.plugins.vixcron.user_command.value = ''
		if config.plugins.vixcron.default_command.value == 'None' and config.plugins.vixcron.user_command.value == '':
			msg = 'You must set at least one Command'
			config.plugins.vixcron.user_command.value = 'None'
		if config.plugins.vixcron.default_command.value != 'None' and config.plugins.vixcron.user_command.value != '':
			msg = 'Entering a Custom command you have to set Predefined command: None '
		if msg:
			self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
		else:
			self.saveMycron()

	def saveMycron(self):
		hour = '%02d' % config.plugins.vixcron.cmdtime.value[0]
		minutes = '%02d' % config.plugins.vixcron.cmdtime.value[1]
		if config.plugins.vixcron.default_command.value != 'None':
			command = config.plugins.vixcron.default_command.value
		else:
			command = config.plugins.vixcron.user_command.value

		if config.plugins.vixcron.runwhen.value == 'Hourly':
			newcron = minutes + ' ' + ' * * * * ' + command.strip() + '\n'
		elif config.plugins.vixcron.runwhen.value == 'Daily':
			newcron = minutes + ' ' + hour + ' * * * ' + command.strip() + '\n'
		elif config.plugins.vixcron.runwhen.value == 'Weekly':
			if config.plugins.vixcron.dayofweek.value == 'Sunday':
				newcron = minutes + ' ' + hour + ' * * 0 ' + command.strip() + '\n'
			elif config.plugins.vixcron.dayofweek.value == 'Monday':
				newcron = minutes + ' ' + hour + ' * * 1 ' + command.strip() + '\n'
			elif config.plugins.vixcron.dayofweek.value == 'Tuesday':
				newcron = minutes + ' ' + hour + ' * * 2 ' + command.strip() + '\n'
			elif config.plugins.vixcron.dayofweek.value == 'Wednesday':
				newcron = minutes + ' ' + hour + ' * * 3 ' + command.strip() + '\n'
			elif config.plugins.vixcron.dayofweek.value == 'Thursday':
				newcron = minutes + ' ' + hour + ' * * 4 ' + command.strip() + '\n'
			elif config.plugins.vixcron.dayofweek.value == 'Friday':
				newcron = minutes + ' ' + hour + ' * * 5 ' + command.strip() + '\n'
			elif config.plugins.vixcron.dayofweek.value == 'Saturday':
				newcron = minutes + ' ' + hour + ' * * 6 ' + command.strip() + '\n'
		elif config.plugins.vixcron.runwhen.value == 'Monthly':
			newcron = minutes + ' ' + hour + ' ' + str(config.plugins.vixcron.dayofmonth.value) + ' * * ' + command.strip() + '\n'
		else:
			command = config.plugins.vixcron.user_command.value

		out = open('/etc/cron/crontabs/root', 'a')
		out.write(newcron)
		out.close()
		rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
		config.plugins.vixcron.default_command.value = 'None'
		config.plugins.vixcron.user_command.value = 'None'
		config.plugins.vixcron.runwhen.value = 'Daily'
		config.plugins.vixcron.dayofweek.value = 'Monday'
		config.plugins.vixcron.dayofmonth.value = 1
		config.plugins.vixcron.cmdtime.value, mytmpt = ([0, 0], [0, 0])
		self.close()
