dist_noinst_SCRIPTS = xml2po.py

plugindir = $(libdir)/enigma2/python/Plugins/SystemPlugins/ViX

LANGS = ar bg ca cs da de el en en_GB es et fa fi fr fy he hr hu is it ku lt lv nl no nb pl pt pt_BR ro ru sv sk sl sr th tr uk
LANGMO = $(LANGS:=.mo)
LANGPO = $(LANGS:=.po)

EXTRA_DIST = $(LANGPO)

# the TRANSLATORS: allows putting translation comments before the to-be-translated line.
vix-py.pot: $(top_srcdir)/src/*.py
	$(XGETTEXT) --no-wrap -L Python --from-code=UTF-8 --add-comments="TRANSLATORS:" -d @PACKAGE_NAME@ -s -o $@ $^

vix-xml.pot: $(srcdir)/xml2po.py $(top_srcdir)/src/*.xml
	$(PYTHON) $^ > $@

vix.pot: vix-py.pot vix-xml.pot
	sed --in-place vix-py.pot --expression=s/CHARSET/UTF-8/
	sed --in-place vix-xml.pot --expression=s/CHARSET/UTF-8/
	cat $^ | $(MSGUNIQ) --no-wrap --no-location -o $@ -

%.po: vix.pot
	if [ -f $@ ]; then \
		$(MSGMERGE) --backup=none --no-wrap --no-location -s -N -U $@ $< && touch $@; \
	else \
		$(MSGINIT) -l $@ -o $@ -i $< --no-translator; \
	fi

.po.mo:
	$(MSGFMT) -o $@ $<

BUILT_SOURCES = $(LANGMO)
CLEANFILES = $(LANGMO) vix-py.pot vix.pot

dist-hook: $(LANGPO)

install-data-local: $(LANGMO)
	for lang in $(LANGS); do \
		$(mkinstalldirs) $(DESTDIR)$(plugindir)/locale/$$lang/LC_MESSAGES; \
		$(INSTALL_DATA) $$lang.po $(DESTDIR)$(plugindir)/locale/vix-$$lang.po; \
		$(INSTALL_DATA) $$lang.mo $(DESTDIR)$(plugindir)/locale/$$lang/LC_MESSAGES/vix.mo; \
	done

uninstall-local:
	for lang in $(LANGS); do \
		$(RM) $(DESTDIR)$(plugindir)/locale/vix-$$lang.po; \
		$(RM) $(DESTDIR)$(plugindir)/locale/$$lang/LC_MESSAGES/vix.mo; \
	done
