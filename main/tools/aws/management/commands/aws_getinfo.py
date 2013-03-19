import boto.ec2
from boto.ec2 import EC2Connection
import boto.ec2.elb
from boto.ec2.elb import ELBConnection
from boto.exception import BotoServerError
from optparse import make_option
import re
import socket
import sys

from django.core.management.base import BaseCommand, CommandError

import settings


BASEREF = '.c2gops.com' # FIXME: configurable baseref?
RE_NAMECLASS = re.compile('^(?P<class>\D+)\d+')


def get_my_private_ip():
    """Returns the ip address that routes to the outside world
    
    Note - this is the local address that routes to outside, not the outside
    address that routes to local
    """
    # NB: Doesn't actually create a connection, just does set up and teardown
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))    # google DNS
    my_ip = s.getsockname()[0]
    s.close()
    return my_ip

class Command(BaseCommand):
    args = ""
    help = """Write information about this host and its neighbors to disk
    
    Assumes our outbound IP address is a private address that is the same registered internally with Amazon
    Assumes we've tagged instances with a Name, and that the name is used to build the hostname
    Assumes the name of the security group of the instance matches the name of the load balancer
    """

    option_list = (
            make_option("-d", "--debug", dest="DEBUG", default=False, action="store_true", help="Run ipdb on exceptions; add extra tracing"),
            make_option("-e", "--erlangfile", dest="erlfile", default='', help="Write output in Erlang's hosts format to file <erlangfile>"),
            make_option("-c", "--csvfile", dest="csvfile", default='', help="Write output as csv to file <outfile>"),
            make_option("-h", "--hostsfile", dest="hostsfile", default='', help="Write output in hosts format to file <hostsfile>"),
            make_option("-C", "--thisclass", dest="thisclass", default=False, action="store_true", help="Limit output to hosts in this class (app, util)"),
    ) + BaseCommand.option_list

    def handle(self, *args, **options):
        ec2_connection = EC2Connection(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        regions = boto.ec2.elb.regions()
        my_priv_ip = get_my_private_ip()
        if options['DEBUG']:
            sys.stderr.write("self=%s\n" % my_priv_ip)
        outputs = {}
        if options['erlfile']:
            outputs['erl'] = open(options['erlfile'], 'wb')
        if options['csvfile']:
            outputs['csv'] = open(options['csvfile'], 'wb')
        if options['hostsfile']:
            outputs['hosts'] = open(options['hostsfile'], 'wb')
        if not outputs:
            outputs['out'] = sys.stdout

        for region in regions:
            region_lb_connection = ELBConnection(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, region=region)
            # regions is a list of RegionInfo with connection_cls ELBConnection
            # so for our EC2Connection we want to get an EC2Connection RegionInfo with the corresponding region descriptor
            region_connection = EC2Connection(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, region=boto.ec2.get_region(region.name))

            load_balancers = region_lb_connection.get_all_load_balancers()
            instances = [r.instances[0] for r in region_connection.get_all_instances()]
            try:
                me = [i for i in instances if i.private_ip_address == my_priv_ip][0]
                my_main_group = me.groups[0].name
            except IndexError:
                me = None
                my_main_group = 'dev'
            instances = [i for i in instances if i.state != u'stopped' and i.groups[0].name == my_main_group and i.tags.get('Name', False)]
            load_balancers = [lb for lb in load_balancers if lb.name == my_main_group]
            meclass = 'app'
            if me and options['thisclass']:
                m = RE_NAMECLASS.match(me.tags.get('Name', ''))
                if m:
                    meclass = m.groups('class')
            instances = [i for i in instances if i.tags['Name'].startswith(meclass)]

            if load_balancers:
                if 'out' in outputs:
                    outputs['out'].write("%s %s %s\n" % (meclass, region, load_balancers[0]))
                for instance in instances:
                    i_name = ''.join((instance.tags['Name'], BASEREF))
                    if 'erl' in outputs:
                        outputs['erl'].write("'%s'.\n" % i_name)
                    if 'csv' in outputs:
                        outputs['csv'].write("%s, %s, %s, %s\n" % (instance.tags['Name'], instance.ip_address, instance.public_dns_name, i_name))
                    if 'hosts' in outputs:
                        outputs['hosts'].write("%s %s\n" % (instance.ip_address, i_name))
                    if 'out' in outputs:
                        outputs['out'].write("%s, %s, %s, %s\n" % (instance.tags['Name'], instance.ip_address, instance.public_dns_name, i_name))
                    # TODO: we could do a set of socket connections to confirm that it's up on some set of ports we care about
