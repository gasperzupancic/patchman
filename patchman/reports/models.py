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

from django.db import models, IntegrityError, DatabaseError, transaction

from patchman.hosts.models import Host
from patchman.arch.models import MachineArchitecture
from patchman.operatingsystems.models import OS
from patchman.domains.models import Domain
from patchman.signals import error_message, info_message

from socket import gethostbyaddr


class Report(models.Model):

    created = models.DateTimeField(auto_now_add=True)
    accessed = models.DateTimeField(auto_now_add=True)
    host = models.CharField(max_length=255, null=True)
    domain = models.CharField(max_length=255, null=True)
    tags = models.CharField(max_length=255, null=True, default='')
    kernel = models.CharField(max_length=255, null=True)
    arch = models.CharField(max_length=255, null=True)
    os = models.CharField(max_length=255, null=True)
    report_ip = models.GenericIPAddressField(null=True)
    protocol = models.CharField(max_length=255, null=True)
    useragent = models.CharField(max_length=255, null=True)
    processed = models.BooleanField(default=False)
    packages = models.TextField(null=True, blank=True)
    sec_updates = models.TextField(null=True, blank=True)
    bug_updates = models.TextField(null=True, blank=True)
    repos = models.TextField(null=True, blank=True)
    reboot = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Report'
        verbose_name_plural = 'Reports'
        ordering = ('-created',)

    def __unicode__(self):
        return '%s %s' % (self.host, self.created)

    @models.permalink
    def get_absolute_url(self):
        return ('report_detail', [self.id])

    def parse(self, data, meta):

        self.report_ip = meta['REMOTE_ADDR']
        self.useragent = meta['HTTP_USER_AGENT']
        self.domain = None

        attrs = ['arch', 'host', 'os', 'kernel', 'protocol', 'packages',
                 'tags', 'sec_updates', 'bug_updates', 'repos', 'reboot']

        for attr in attrs:
            setattr(self, attr, data.get(attr))

        if self.host is not None:
            fqdn = self.host.split('.', 1)
            if len(fqdn) == 2:
                self.domain = fqdn.pop()

        with transaction.atomic():
            self.save()

    def process(self, find_updates=True, verbose=False):
        """ Process a report and extract os, arch, domain, packages, repos etc
        """

        if self.os and self.kernel and self.arch and not self.processed:

            oses = OS.objects.all()
            with transaction.atomic():
                os, c = oses.get_or_create(name=self.os)

            machine_arches = MachineArchitecture.objects.all()
            with transaction.atomic():
                arch, c = machine_arches.get_or_create(name=self.arch)

            if not self.domain:
                self.domain = 'unknown'
            domains = Domain.objects.all()
            with transaction.atomic():
                domain, c = domains.get_or_create(name=self.domain)

            if not self.host:
                try:
                    self.host = str(gethostbyaddr(self.report_ip)[0])
                except:
                    self.host = self.report_ip

            hosts = Host.objects.all()
            with transaction.atomic():
                host, c = hosts.get_or_create(
                    hostname=self.host,
                    defaults={
                        'ipaddress': self.report_ip,
                        'arch': arch,
                        'os': os,
                        'domain': domain,
                        'lastreport': self.created,
                    })

            host.ipaddress = self.report_ip
            host.kernel = self.kernel
            host.arch = arch
            host.os = os
            host.domain = domain
            host.lastreport = self.created
            host.tags = self.tags
            if self.reboot == 'True':
                host.reboot_required = True
            else:
                host.reboot_required = False
            try:
                with transaction.atomic():
                    host.save()
            except IntegrityError as e:
                print e
            except DatabaseError as e:
                print e
            host.check_rdns()

            if verbose:
                print 'Processing report %s - %s' % (self.id, self.host)

            from patchman.reports.utils import process_packages, \
                process_repos, process_updates
            with transaction.atomic():
                process_repos(report=self, host=host)
            with transaction.atomic():
                process_packages(report=self, host=host)
            with transaction.atomic():
                process_updates(report=self, host=host)

            self.processed = True
            with transaction.atomic():
                self.save()

            if find_updates:
                if verbose:
                    print 'Finding updates for report %s - %s' % \
                        (self.id, self.host)
                host.find_updates()
        else:
            if self.processed:
                text = 'Report %s has already been processed\n' % (self.id)
                info_message.send(sender=None, text=text)
            else:
                text = 'Error: OS, kernel or arch not sent with report %s\n' \
                    % (self.id)
                error_message.send(sender=None, text=text)
