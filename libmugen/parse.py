"""
This class is released under the same license as the python library configparser
leif theden, 2012 - 2016
"""

import re
import sys
from configparser import DuplicateOptionError, DuplicateSectionError, RawConfigParser, SectionProxy


class MugenParser(RawConfigParser):
    def __init__(self):
        super().__init__(inline_comment_prefixes=(';', '#', ':'),
                         comment_prefixes=(';', '#', ':'),
                         strict=False)

        # allow case headers with extra space (it happens...)
        self.SECTCRE = re.compile(r"\[ *(?P<header>[^]]+?) *\]")

    def _read(self, fp, fpname):
        """ MUGEN flavored configuration parsing

        Parse a sectioned configuration file.

        Each section in a configuration file contains a header, indicated by
        a name in square brackets (`[]'), plus key/value options, indicated by
        `name' and `value' delimited with a specific substring (`=' or `:' by
        default).

        Values can span multiple lines, as long as they are indented deeper
        than the first line of the value. Depending on the parser's mode, blank
        lines may be treated as parts of multiline values or ignored.

        Configuration files may include comments, prefixed by specific
        characters (`#' and `;' by default). Comments may appear on their own
        in an otherwise empty line or may be entered in lines holding values or
        section names.
        """
        elements_added = set()
        cursect = None                        # None, or a dictionary
        sectname = None
        optname = None
        indent_level = 0

        # some people like to include credits before the first section header
        # this will accommodate this, even if it is not ini file spec.
        skip_header = True

        e = None                              # None, or an exception
        for lineno, line in enumerate(fp, start=1):
            comment_start = sys.maxsize

            # strip inline comments
            inline_prefixes = {p: -1 for p in self._inline_comment_prefixes}
            while comment_start == sys.maxsize and inline_prefixes:
                next_prefixes = {}
                for prefix, index in inline_prefixes.items():
                    index = line.find(prefix, index + 1)
                    if index == -1:
                        continue
                    next_prefixes[prefix] = index
                    if index == 0 or (index > 0 and line[index - 1].isspace()):
                        comment_start = min(comment_start, index)
                inline_prefixes = next_prefixes

            # strip full line comments
            for prefix in self._comment_prefixes:
                if line.strip().startswith(prefix):
                    comment_start = 0
                    break

            if comment_start == sys.maxsize:
                comment_start = None

            value = line[:comment_start].strip()

            if not value:
                if self._empty_lines_in_values:

                    # add empty line to the value, but only if there was no
                    # comment on the line
                    if (comment_start is None and
                                cursect is not None and
                            optname and
                                cursect[optname] is not None):
                        cursect[optname].append('') # newlines added at join
                else:

                    # empty line marks end of value
                    indent_level = sys.maxsize
                continue

            # continuation line?
            first_nonspace = self.NONSPACECRE.search(line)
            cur_indent_level = first_nonspace.start() if first_nonspace else 0
            if cursect is not None and optname and cur_indent_level > indent_level:
                cursect[optname].append(value)

            # a section header or option header?
            else:
                indent_level = cur_indent_level
                # is it a section header?
                mo = self.SECTCRE.match(value)
                if mo:
                    skip_header = False
                    # LT: lower case section names
                    sectname = mo.group('header').lower()
                    if sectname in self._sections:
                        if self._strict and sectname in elements_added:
                            raise DuplicateSectionError(sectname, fpname,
                                                        lineno)
                        cursect = self._sections[sectname]
                        elements_added.add(sectname)
                    elif sectname == self.default_section:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        self._sections[sectname] = cursect
                        self._proxies[sectname] = SectionProxy(self, sectname)
                        elements_added.add(sectname)

                    # So sections can't start with a continuation line
                    optname = None

                # no section header in the file?
                # just skip it
                elif cursect is None:
                    indent_level = sys.maxsize

                    if not skip_header:
                        sectname = None
                        optname = None
                        cursect = None
                        # raise MissingSectionHeaderError(fpname, lineno, line)

                # an option line?
                else:
                    mo = self._optcre.match(value)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if not optname:
                            e = self._handle_error(e, fpname, lineno, line)
                        optname = self.optionxform(optname.rstrip())
                        if (self._strict and
                                    (sectname, optname) in elements_added):
                            raise DuplicateOptionError(sectname, optname,
                                                       fpname, lineno)
                        elements_added.add((sectname, optname))

                        # This check is fine because the OPTCRE cannot
                        # match if it would set optval to None
                        if optval is not None:
                            optval = optval.strip()
                            cursect[optname] = [optval]
                        else:

                            # valueless option handling
                            cursect[optname] = None
                    else:
                        # a non-fatal parsing error occurred. set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines

                        # LT: allow bogus lines
                        # e = self._handle_error(e, fpname, lineno, line)
                        pass

        # if any parsing errors occurred, raise an exception
        if e:
            raise e
        self._join_multiline_values()
