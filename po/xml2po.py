#!/usr/bin/python
import sys
import os
import string
import re
from xml.sax import make_parser
from xml.sax.handler import ContentHandler, property_lexical_handler

try:
	from _xmlplus.sax.saxlib import LexicalHandler

	no_comments = False
except ImportError:
	class LexicalHandler:
		def __init__(self):
			pass

	no_comments = True


class parseXML(ContentHandler, LexicalHandler):
	def __init__(self, attrlist):
		self.isPointsElement, self.isReboundsElement = 0, 0
		self.attrlist = attrlist
		self.last_comment = None
		self.ishex = re.compile('#[0-9a-fA-F]+\Z')

	def comment(self, comment):
		if comment.find("TRANSLATORS:") != -1:
			self.last_comment = comment

	def startElement(self, name, attrs):
		for x in ["text", "title", "value", "caption", "summary", "description"]:
			try:
				k = str(attrs[x])
				if k.strip() != "" and not self.ishex.match(k):
					attrlist.add((attrs[x], self.last_comment))
					self.last_comment = None
			except KeyError:
				pass


parser = make_parser()

attrlist = set()

contentHandler = parseXML(attrlist)
parser.setContentHandler(contentHandler)
if not no_comments:
	parser.setProperty(property_lexical_handler, contentHandler)

for arg in sys.argv[1:]:
	if os.path.isdir(arg):
		for file in os.listdir(arg):
			if file.endswith(".xml"):
				parser.parse(os.path.join(arg, file))
	else:
		parser.parse(arg)

	attrlist = list(attrlist)
	attrlist.sort(key=lambda a: a[0])

	for (k, c) in attrlist:
		print
		print '#: ' + arg
# We need to escape all "s that we have in the string.
# This replace() *must* come before anything that adds "s!! (such as the
# newline-handling code).
# Ideally we'd do this "intelligently" (check for no current preceding \)
# but there is no reason for there ever to be one, so....
#
		k = str(k).replace('"', '\\"')
		k = k.replace("\\n", "\"\n\"")
		if c:
			for l in c.split('\n'):
				print "#. ", l
		print 'msgid "' + k + '"'
		print 'msgstr ""'

	attrlist = set()
