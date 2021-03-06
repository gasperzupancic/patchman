# Copyright 2012 VPAC, http://www.vpac.org
#
# This file is part of Patchman.
#
# Patchman is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 only.
#
# Patchman is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Patchman. If not, see <http://www.gnu.org/licenses/>

from django.db import models

from rpm import labelCompare
from debian.debian_support import Version, version_compare

from patchman.arch.models import PackageArchitecture
from patchman.packages.managers import PackageManager


class PackageName(models.Model):

    name = models.CharField(unique=True, max_length=255)

    class Meta:
        verbose_name = 'Package'
        verbose_name_plural = 'Packages'
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('package_detail', [self.name])


class Package(models.Model):

    RPM = 'R'
    DEB = 'D'
    UNKNOWN = 'U'

    PACKAGE_TYPES = (
        (RPM, 'rpm'),
        (DEB, 'deb'),
        (UNKNOWN, 'unknown'),
    )

    name = models.ForeignKey(PackageName)
    epoch = models.CharField(max_length=255, blank=True, null=True)
    version = models.CharField(max_length=255)
    release = models.CharField(max_length=255, blank=True, null=True)
    arch = models.ForeignKey(PackageArchitecture)
    packagetype = models.CharField(max_length=1,
                                   choices=PACKAGE_TYPES,
                                   blank=True,
                                   null=True)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=255, blank=True, null=True)

    objects = PackageManager()

    class Meta:
        ordering = ('name', 'epoch', 'version', 'release', 'arch')
        unique_together = (
            'name', 'epoch', 'version', 'release', 'arch', 'packagetype',)

    def __unicode__(self):
        if self.epoch:
            epo = '%s:' % self.epoch
        else:
            epo = ''
        if self.release:
            rel = '-%s' % self.release
        else:
            rel = ''
        return '%s-%s%s%s-%s' % (self.name, epo, self.version, rel, self.arch)

    def get_absolute_url(self):
        return self.name.get_absolute_url()

    def __key(self):
        return (self.name, self.epoch, self.version, self.release, self.arch,
                self.packagetype)

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if not self:
            return 0
        return hash(self.__key())

    def _version_string_rpm(self):
        return (str(self.epoch), str(self.version), str(self.release))

    def _version_string_deb(self):
        epoch = ''
        version = ''
        release = ''
        if self.epoch != '':
            epoch = str(self.epoch) + ':'
        if self.version != '':
            version = str(self.version)
        if self.release != '':
            release = '-' + str(self.release)
        return (epoch + version + release)

    def get_version_string(self):
        if self.packagetype == 'R':
            return self._version_string_rpm()
        elif self.packagetype == 'D':
            return self._version_string_deb()

    def compare_version(self, other):
        if self.packagetype == 'R' and other.packagetype == 'R':
            return labelCompare(self.get_version_string(),
                                other.get_version_string())
        elif self.packagetype == 'D' and other.packagetype == 'D':
            vs = Version(self.get_version_string())
            vo = Version(other.get_version_string())
            return version_compare(vs, vo)

    def repo_count(self):
        from patchman.repos.models import Repository
        return Repository.objects.filter(
            mirror__packages=self).distinct().count()


class PackageString(models.Model):

    class Meta:
        managed = False

    name = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    epoch = models.CharField(max_length=255, blank=True, null=True)
    release = models.CharField(max_length=255, blank=True, null=True)
    arch = models.CharField(max_length=255)
    packagetype = models.CharField(max_length=1, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=255, blank=True, null=True)

    def __unicode__(self):
        if self.epoch:
            epo = '%s:' % self.epoch
        else:
            epo = ''
        if self.release:
            rel = '-%s' % self.release
        else:
            rel = ''
        return '%s-%s%s%s-%s' % (self.name, epo, self.version, rel, self.arch)

    def __key(self):
        return (self.name, self.epoch, self.version, self.release, self.arch,
                self.packagetype)

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if not self:
            return 0
        return hash(self.__key())


class PackageUpdate(models.Model):

    oldpackage = models.ForeignKey(Package, related_name='oldpackage')
    newpackage = models.ForeignKey(Package, related_name='newpackage')
    security = models.BooleanField(default=False)

    class Meta:
        unique_together = (('oldpackage', 'newpackage', 'security'))

    def __unicode__(self):
        if self.security:
            update_type = 'Security'
        else:
            update_type = 'Bugfix'
        return '%s -> %s (%s)' % (self.oldpackage, self.newpackage,
                                  update_type)
