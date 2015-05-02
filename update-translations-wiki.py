# -*- coding: utf-8 -*-
##
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

import tarfile
import dircache
import socket
import logging
from optparse import OptionParser
from ConfigParser import ConfigParser
from sys import argv, exit
from urllib2 import urlopen
from os import path, mkdir, listdir, unlink, rmdir
from time import time, sleep
from editmoin import editshortcut
from BeautifulSoup import BeautifulSoup

logger = logging.getLogger("update_translations_wiki")
logging.basicConfig(level=logging.ERROR)


def setUp(file="/media/files/Projects/rosetta2wiki/devel/wiki.conf"):
    try:
        parser = ConfigParser()
        parser.readfp(open(file))
        return parser
    except IOError:
        print "Config file not found: %s" % file
        exit(1)


class PackagesList():

    def __init__(self, file=""):
        self.packages = self.get_list(file)

    def get_list(self, file):
        # current working directory
        cwd = path.dirname(path.realpath(__file__))
        try:
            package_list = open(path.join(cwd, file)).readlines()
            packages = {}
            for item in package_list:
                packages[item.split()[1]] = item.split()[0]
            return packages
        except:
            pass


class GnomePackagesList(PackagesList):

    def __init__(self, project="gnome"):
        self.project = project
        # XXX: pegar do arquivo de configuração também
        self.download_link = (
            "http://l10n.gnome.org/languages/pt_BR/gnome-2-28/ui.tar.gz")
        self.dir_name = ""
        self.tarfile_name = ""
        self.set_env()
        self.tarfile_path = path.join(self.dir_name, self.tarfile_name)
        self.packages = self.get_list()
        self.unset_env()

    def set_env(self):
        try:
            dir_name = str(int(time()))
            mkdir(dir_name)
            self.dir_name = dir_name
            self.tarfile_name = path.basename(self.download_link)
        except IOError, e:
            print "Problems creating %s: %s" % (dir_name, e)

    def download_file(self):
        try:
            answer = urlopen(self.download_link)
            file = open(self.tarfile_path, 'wb')
            file.write(answer.read())
            file.close()
        except Exception, e:
            print "Error downloading file from %s: %s" % (
                self.download_link, e)
            print "Will continue, without removing gnome packages."
            raise e

    def extract(self):
        tar = tarfile.open(self.tarfile_path)
        tar.extractall(path=self.dir_name)
        tar.close()
        return self.dir_name

    def download_list(self, project="gnome"):
        try:
            self.download_file()
        except:
            return []
        return listdir(self.extract())

    def get_list(self):
        packages = self.download_list()
        if len(packages) == 0:
            return packages
        self.delete(self.tarfile_path)
        gnome_packages = []
        for item in packages:
            package = item.split(".")[0].replace(
                "-2.0", "").replace("-2.2", "")
            gnome_packages.append(package)
        return gnome_packages

    def recursive_delete(self, dirname):
        files = dircache.listdir(dirname)
        for file in files:
            path_ = path.join(dirname, file)
            if path.isdir(path_):
                self.recursive_delete(path_)
            else:
                retval = self.delete(path_)
        rmdir(dirname)
        return retval

    def delete(self, filename):
        unlink(filename)

    def unset_env(self):
        self.recursive_delete(self.dir_name)


class Wiki():

    def __init__(self, packages_list, ubuntu_series, stats):
        self.stats = stats
        self.header = configs.get("general", "header")
        self.packages = packages_list
        self.ubuntu_series = ubuntu_series.lower()
        self.translation_page_root = (
            "%s/ubuntu/%s/+lang/pt_BR/+index" % (
                configs.get("general", "rosetta_root_link"),
                self.ubuntu_series))
        self.wiki_link = (
            "%s/TimeDeTraducao/%sPacotes" % (configs.get(
                "general", "wiki_root_link"), ubuntu_series.title()))

    def publish_to_wiki(self):
        def editfunc(moinfile):
            if "This page was opened for editing" in moinfile.data:
                # Cancel the editing.
                return 0
            self.add_content_to_page(moinfile)
            return 1

        if not editshortcut(self.wiki_link, editfile_func=editfunc):
            # Some one else was editing the page. Raise an exception
            raise Exception(
                "Couldn't get write lock for the wiki page. Aborting.")

    def add_content_to_page(self, moinfile):
        """Add the stats and packages to the wiki page."""
        # The current body has come characters escaped.
        stats = self.stats
        new_packages = self.packages
        lines = moinfile._unescape(moinfile.body).splitlines()

        # Remove the old stats:
        start_index = lines.index("##STATS_START") + 1
        end_index = lines.index("##STATS_END")
        for line in lines[start_index:end_index]:
            lines.remove(line)

        # Add the new ones:
        lines.insert(start_index, stats)

        # Remove the old packages:
        start_pkg_index = lines.index("##LIST_START") + 1
        new_page = lines[0:start_pkg_index]

        # Add the new ones:
        new_page.extend(new_packages)

        # Even though we unescaped the body before editing it, we don't need
        # to escape it again now.
        moinfile.body = '\n'.join(new_page)


class Package():

    def __init__(
            self, name, pkg_link, total_strings_count, untranslated_count,
            needs_review_count, rosetta_root_link):
        self.name = name
        self.pkg_link = pkg_link
        self.root_link = rosetta_root_link
        self.total_strings_count = total_strings_count
        self.untranslated_strings_count = untranslated_count
        self.needs_review_count = needs_review_count
        self.is_gnome = False
        self.is_reviewed = False
        self.is_affected = False
        self.is_completed = False

    def format_to_wiki(self):
        wiki_line = ""
        link = "%s%s" % (self.root_link, self.pkg_link)
        if not self.is_completed:
            perc_untranslated = (
                self.untranslated_strings_count * 100)/self.total_strings_count
            wiki_line = (
                "|| [[%s | %s]] || %d || [[%s?show=untranslated | %d]] ||"
                "%.2f ||") % (link, self.name, self.total_strings_count, link,
                              self.untranslated_strings_count,
                              perc_untranslated)
        else:
            wiki_line = (
                "|| [[%s | %s]] || %d || [[%s]] || - ||" % (
                    link, self.name, self.total_strings_count, link))
        return wiki_line.encode('UTF-8')

    def format_unreviewed_to_wiki(self):
        wiki_line = ""
        link = "%s%s" % (self.root_link, self.pkg_link)
        wiki_line = (
            "|| [[%s | %s]] || %d || [[%s?show=new_suggestions | %d]] "
            "|| - ||" % (link, self.name, self.total_strings_count,
                         link, self.needs_review_count))
        return wiki_line.encode('UTF-8')

    @property
    def is_pending_review(self):
        return (self.needs_review_count != 0)


class Utils():

    def __init__(self, nick_ubuntu_version):
        logger.debug("Fetching gnome packages..")
        self.gnome_packages = GnomePackagesList().packages
        logger.debug("Done.")
        self.reviewed_packages = PackagesList("pacotes_revisados").packages
        self.affected_packages = PackagesList("pacotes_afetados").packages
        self.translation_page_root = (
            "%s/ubuntu/%s/+lang/pt_BR/+index" % (
                configs.get("general", "rosetta_root_link"),
                nick_ubuntu_version.lower()))
        try:
            self.all_packages = self.handle_rosetta_pages()
            self.pending_list = [
                pkg for pkg in self.all_packages if not (
                    pkg.is_gnome or pkg.is_completed or pkg.is_affected)]
        except Exception:
            raise

    @property
    def all_needs_review(self):
        return [pkg for pkg in self.all_packages if pkg.is_pending_review]

    def is_gnome(self, package):
        return package in self.gnome_packages

    def rosetta_soup(self, start=0, batch=50):
        url = "%s?start=%d&batch=%d" % (
            self.translation_page_root, start, batch)
        urldata = urlopen(url)
        html = "".join(["%s" % line for line in urldata.readlines()])
        return BeautifulSoup(html)

    @property
    def is_reviewed(self, package):
        return package in self.reviewed_packages.values()

    def is_affected(self, link):
        return link in self.affected_packages.keys()

    def handle_rosetta_pages(self):
        logger.debug(
            "The hardest part now: fetching info from launchpad. This"
            " may take a while.. ")
        batch_size = int(configs.get("general", "batch_size"))
        timeout = int(configs.get("general", "timeout"))
        rosetta_root_link = configs.get("general", "rosetta_root_link")
        socket.setdefaulttimeout(timeout)

        all_packages = []
        soup = self.rosetta_soup()
        aux = soup.find(
            name="td", attrs={"class": "batch-navigation-index"}).contents[4]

        total_pacotes = int(aux.strip().split()[1])
        numero_paginas = total_pacotes / batch_size

        logger.debug("Pages to process: %d" % numero_paginas)

        for i in range(1, numero_paginas + 2):
            logger.debug("Processing page %d .. " % i)
            # Tabela de pacotes
            translations_table = soup.find(
                name="table",
                attrs={"class": "listing sortable translation-stats"})
            if translations_table is None:
                if "There are no programs to be translated" in soup:
                    print "Acabaram as páginas!"
                    continue

            # Linhas da tabela
            try:
                lines = translations_table.findAll(name="tr")
            except Exception, e:
                print "Erro obtendo tabela de traducao: %s" % e
                raise
                break

            # Por linha:
            # 0 - nome pacote e link
            # 1 - total de strings
            # 2 - status
            # 3 - numero de strings untranslated
            # 4 - needs review
            # 5 - changed
            # 6 - last edited
            # 7 - by

            # Removendo a primeira linha da tabela, onde está o cabeçalho
            lines.pop(0)

            for line in lines:

                line = line.findAll(name="td")

                # 0 - nome pacote e link
                aux = line[0].find(name='a')
                if aux is None:
                    continue
                pkg_link = aux.attrs[0][1]
                pacote = aux.contents[0].replace(
                    "-2.0", "").replace("-2.2", "")

                # 1 - numero total de strings do pacote
                # De qualquer forma vou somar o numero total de strings
                total_pkg_strings = float(line[1].contents[0])

                # 3 - numero de strings untranslated
                total_pkg_untranslated = float(
                    line[3].find(name="span").contents[0])

                # 4 - numero de strings necessitando revisão (needs review):
                strings_needsreview = float(
                    line[4].find(name="span").contents[0])

                pkg = Package(
                    pacote,
                    pkg_link,
                    total_pkg_strings,
                    total_pkg_untranslated,
                    strings_needsreview,
                    rosetta_root_link)

                pkg.is_gnome = self.is_gnome(pkg.name)
                pkg.is_completed = (pkg.untranslated_strings_count == 0)
                pkg.is_reviewed = (pkg.needs_review_count == 0)
                pkg.is_affected = self.is_affected(pkg.pkg_link)

                all_packages.append(pkg)

            if (i == (numero_paginas + 1)):
                break
            sleep(5)
            ok = False

            while not ok:
                try:
                    soup = self.rosetta_soup(i*batch_size, batch_size)
                    ok = True
                except Exception, e:
                    print "Oops, we have a problem here!"
                    print "Error: %s" % e
                    print "Will sleep for a minute for it to settle."
                    sleep(1)
                    print "Retrying... "
            logger.debug("Done.")

        return all_packages

    def calculate_stats(self):
        gnome_packages = self.gnome_packages
        # self.reviewed_packages = PackagesList("pacotes_revisados").packages
        # self.affected_packages = PackagesList("pacotes_afetados").packages
        all_packages = self.all_packages

        total_strings = sum(
            [string.total_strings_count for string in self.all_packages])
        total_untranslated = sum(
            [string.untranslated_strings_count for string in self.pending_list]
            )
        perc_untranslated = (total_untranslated * 100)/total_strings

        self.total_strings = total_strings
        self.total_untranslated = total_untranslated
        self.perc_untranslated = perc_untranslated

        estatisticas = (
            "{{attachment:Icones/idiomas.png}} '''Estatísticas: %d de"
            " %d strings para traduzir, apenas %.2f porcento.'''" %
            (total_untranslated, total_strings, perc_untranslated))
        estatisticas = (
            "%s<<BR>>\nRestam '''%d''' pacotes para serem"
            " traduzidos.<<BR>><<BR>>" % (
                estatisticas, len(self.pending_list)))
        return estatisticas

    def generate_header(self):
        pass


def main(argv):
    global configs
    configs = setUp()

    description = (
        "This script updates the wiki page that contains the status"
        " of the translations for a given Ubuntu series.")
    usage = "usage: %prog -[vV]"
    parser = OptionParser(description=description, usage=usage)
    parser.add_option(
        '-v', '--verbose', action='store_true', dest='verbose', default=False)
    parser.add_option(
        '-S', '--series', type='string', dest='ubuntu_series')
    parser.add_option(
        '-V', '--very-verbose', action='store_true', dest='very_verbose',
        default=False)
    parser.add_option(
        '-q', '--quiet', action='store_true', dest='quiet', default=False)
    parser.add_option(
        '--needs-review', action='store_true', dest='needs_review',
        default=False)

    options, args = parser.parse_args(argv[1:])
    nick_ubuntu_versions = ["lucid", "maverick", "natty", "oneiric"]

    if options.ubuntu_series:
        ubuntu_serieses = options.ubuntu_series.split(",")
        for serie in ubuntu_serieses:
            if serie.strip() in nick_ubuntu_versions:
                continue
            else:
                logger.critical(
                    "%s not valid. Valid Ubuntu series are: %s." % (
                        serie, ", ".join(nick_ubuntu_versions)))
                exit(1)
    else:
        logger.critical(
            "Ubuntu series required. Valid Ubuntu series are: %s." %
            ", ".join(nick_ubuntu_versions))
        exit(1)

    if options.very_verbose:
        logger.setLevel(logging.DEBUG)
    elif options.verbose:
        logger.setLevel(logging.INFO)
    elif options.quiet:
        logger.setLevel(logging.CRITICAL)
    else:
        logger.setLevel(logging.ERROR)

    logger.debug("Ubuntu versions: %s" % ', '.join(ubuntu_serieses))

    try:
        for ubuntu_version in ubuntu_serieses:
            logger.debug("Version: %s" % ubuntu_version)
            utils = Utils(ubuntu_version)

            if options.needs_review:
                for pkg in utils.all_needs_review:
                    print pkg.format_unreviewed_to_wiki()
            else:
                stats = utils.calculate_stats()

                # Generate the list of packages yet to be translated
                wiki_list = [
                    pkg.format_to_wiki() for pkg in utils.all_packages if not (
                        pkg.is_gnome or pkg.is_completed or pkg.is_affected)]

                # Open wiki page
                wiki = Wiki(wiki_list, ubuntu_version, stats)
                wiki.publish_to_wiki()
    except NameError, e:
        print e
    except AttributeError, e:
        print e
    except ValueError, e:
        print e
    except Exception, e:
        try:
            if e.errno == '503':
                print "%s is not ready yet for translations." % ubuntu_version
        except:
            print e


if __name__ == "__main__":
    main(argv)
