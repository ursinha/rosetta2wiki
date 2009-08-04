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
from ConfigParser import ConfigParser
from sys import exit
from urllib2 import urlopen
from os import path, mkdir, listdir, unlink, rmdir
from time import time, sleep
from editmoin import editshortcut
from BeautifulSoup import BeautifulSoup

import pdb

def setUp(self, file = "wiki.conf"):
    try:
        self.parser = ConfigParser.read(file)
    except IOError:
        print "Config file not found: %s" % file
        exit(1)


class PackagesList():

    def __init__(self, file = ""):
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
        self.download_link = "http://l10n.gnome.org/languages/pt_BR/gnome-2-28/ui.tar.gz"
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
        except:
            pass

    def extract(self):
        tar = tarfile.open(self.tarfile_path)
        tar.extractall(path=self.dir_name)
        tar.close()
        return self.dir_name

    def download_list(self, project="gnome"):
        self.download_file()
        return listdir(self.extract())

    def get_list(self):
        packages = self.download_list()
        self.delete(self.tarfile_path)
        gnome_packages = []
        for item in packages:
            package = item.split(".")[0].replace("-2.0", "")
            gnome_packages.append(package)
        return gnome_packages

    def recursive_delete(self, dirname):
        files = dircache.listdir(dirname)
        for file in files:
            path_ = path.join(dirname, file)
            if path.isdir(path_):
                recursive_delete(path_)
            else:
                retval = self.delete(path_)
        rmdir(dirname)

    def delete(self, filename):
        unlink(filename)

    def unset_env(self):
        self.recursive_delete(self.dir_name)


class Wiki():

    def __init__(self, header, packages_list):
        self.header = header
        self.packages = packages_list

    def publish_to_wiki(self):
        pass

    def editfunc(moinfile):
        if "This page was opened for editing" in moinfile.data:
            return 0
        edit_page(moinfile, wiki_link)
        return 1

    def editfunc_needsreview(moinfile):
        if "This page was opened for editing" in moinfile.data:
            return 0
        edit_page_needsreview(moinfile, wiki_link_needsreview)
        return 1

    def editfunc_reviewed(moinfile):
        if "This page was opened for editing" in moinfile.data:
            return 0
        edit_page_reviewed(moinfile, wiki_link_reviewed)
        return 1

    def edit_page(moinfile, link):
        """Adiciona o conteudo alterado do wiki na pagina."""
        moinfile.body = '\n'.join(wiki_lines)

    def edit_page_needsreview(moinfile, link):
        """Adiciona o conteudo alterado do wiki na pagina."""
        moinfile.body = '\n'.join(wiki_lines_needsreview)

    def edit_page_reviewed(moinfile, link):
        """Adiciona o conteudo alterado do wiki na pagina."""
        moinfile.body = '\n'.join(wiki_lines_reviewed)


class Package():

    def __init__(self, name, pkg_link, total_strings_count, untranslated_count,
            needs_review_count):
        self.name = name
        self.pkg_link = pkg_link
        self.total_strings_count = total_strings_count
        self.untranslated_strings_count = untranslated_count
        self.needs_review_count = needs_review_count
        self.is_gnome = False
        self.is_reviewed = False
        self.is_affected = False
        self.is_completed = False

    def format_to_wiki(self):
        wiki_line = ""
        link = "%s%s" % (root_link, self.pkg_link)
        if not self.is_completed:
            perc_untranslated = (self.untranslated_strings_count *
                    100)/self.total_strings_count
            wiki_line = "|| [%s %s] || %d || [%s?show=untranslated %d] || %.2f ||" %\
                    (link, self.name, self.total_strings_count, link,
                    self.untranslated_strings_count, perc_untranslated)
        else:
            wiki_line = "|| [%s %s] || %d || [%s] || - ||" %\
                    (link, self.name, self.total_strings_count, link)
        return wiki_line


class Utils():

    def __init__(self):
        self.gnome_packages = GnomePackagesList().packages
        self.reviewed_packages = PackagesList("pacotes_revisados").packages
        self.affected_packages = PackagesList("pacotes_afetados").packages
        self.all_packages = self.handle_rosetta_pages()

    def is_gnome(self, package):
        return package in self.gnome_packages

    def rosetta_soup(self, start=0, batch=50):
        translation_page_root = ("https://translations.edge.launchpad.net/"
            "ubuntu/karmic/+lang/pt_BR/+index")
        url = "%s?start=%d&batch=%d" % (translation_page_root, start, batch)
        print url
        urldata = urlopen(url)
        html = "".join(["%s" % line for line in urldata.readlines()])
        return BeautifulSoup(html)

    @property
    def is_reviewed(self, package):
        return package in self.reviewed_packages.values()

    def is_affected(self, link):
        return link in self.affected_packages.keys()

    def handle_rosetta_pages(self):
        batch_size = 50
        timeout = 60
        socket.setdefaulttimeout(timeout)
        
        all_packages = []
        soup = self.rosetta_soup()
        aux = soup.find(name="td",
            attrs={"class":"batch-navigation-index"}).contents[4]

        total_pacotes = int(aux.strip().split()[1])
        numero_paginas = total_pacotes / batch_size

        for i in range(1, numero_paginas + 2):
            # Tabela de pacotes
            translations_table = soup.find(name="table", attrs={"id":"translationstatuses"})
            # Linhas da tabela
            lines = translations_table.findAll(name="tr")

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
                pkg_link = aux.attrs[0][1]
                pacote = aux.contents[0].replace("-2.0", "")

                # 1 - numero total de strings do pacote
                # De qualquer forma vou somar o numero total de strings
                total_pkg_strings = float(line[1].contents[0])

                # 3 - numero de strings untranslated
                total_pkg_untranslated = float(line[3].find(name="span").contents[0])

                # 4 - numero de strings necessitando revisão (needs review):
                strings_needsreview = float(line[4].find(name="span").contents[0])

                if total_pkg_untranslated == 0 or self.is_affected(pkg_link):
                    continue

                pkg = Package(pacote.replace("-2.0", ""), pkg_link,
                        total_pkg_strings,
                        total_pkg_untranslated,
                        strings_needsreview)

                pkg.is_gnome = self.is_gnome(pkg.name)
                pkg.is_completed = pkg.untranslated_strings_count == 0
                pkg.is_reviewed = pkg.needs_review_count == 0
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
                    sleep(60)
                    print "Retrying... "

        return all_packages

root_link = "https://translations.launchpad.net"
utils = Utils()

## Adicionando as estatisticas:
#porcentagem_untranslated = (total_untranslated * 100)/total_strings
#estatisticas = "attachment:Icones/idiomas.png '''Estatísticas: %d de %d
#strings para traduzir, apenas %.2f porcento.'''" %\
#    (total_untranslated, total_strings, porcentagem_untranslated)
#estatisticas = "%s[[BR]]\nRestam '''%d''' pacotes para serem
#traduzidos.[[BR]][[BR]]" %\
#    (estatisticas, pacotes_a_traduzir)

# imprimir lista de pacotes para traduzir ainda
wiki_list = [pkg for pkg in utils.all_packages if not (pkg.is_gnome or
        pkg.is_completed)]
for pkg in wiki_list:
    print pkg.format_to_wiki()

print "\n\nGnome list:\n"
# fazer lista de pacotes do gnome e remove-los da lista geral
gnome_list = [pkg for pkg in utils.all_packages if (pkg.is_gnome and
        not pkg.is_completed)]
for pkg in gnome_list:
    print pkg.format_to_wiki()

