AC_INIT(plugins,0.0.1)
AM_INIT_AUTOMAKE(plugins,0.0.1)

TUXBOX_APPS_DIRECTORY

AC_PATH_PROG(MSGFMT, msgfmt, AC_MSG_ERROR(Could not find msgfmt))

AM_PATH_PYTHON
AC_PYTHON_DEVEL

AC_PROG_CXX

CPPFLAGS="$CPPFLAGS $PYTHON_CPPFLAGS"
LDFLAGS="$LDFLAGS $PYTHON_LDFLAGS"

AC_PATH_PROG(MSGFMT, msgfmt, AC_MSG_ERROR(Could not find msgfmt))
AC_PATH_PROG(MSGINIT, msginit, AC_MSG_ERROR(Could not find msginit))
AC_PATH_PROG(MSGMERGE, msgmerge, AC_MSG_ERROR(Could not find msgmerge))
AC_PATH_PROG(MSGUNIQ, msguniq, AC_MSG_ERROR(Could not find msguniq))
AC_PATH_PROG(XGETTEXT, xgettext, AC_MSG_ERROR(Could not find xgettext))

AC_OUTPUT([
Makefile
etc/Makefile
etc/cron/Makefile
etc/cron/crontabs/Makefile
po/Makefile
src/Makefile
src/images/Makefile
])
