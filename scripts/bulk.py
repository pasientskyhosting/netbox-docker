import netaddr
import csv
from dcim.choices import InterfaceTypeChoices, InterfaceModeChoices
from dcim.models import Platform, DeviceRole, Site
from ipam.models import IPAddress, VRF, Interface, Prefix
from tenancy.models import Tenant
from virtualization.models import VirtualMachine, Cluster
from virtualization.choices import VirtualMachineStatusChoices
from extras.scripts import Script, TextVar
from extras.models import Tag


class VM:

    __staged_hostnames: []
    status: str
    tenant: Tenant
    cluster: Cluster
    site: Site
    ip_address: IPAddress

    DEFAULT_TAGS = ['ansible', 'zero_day']
    DEFAULT_DOMAIN_PRIVATE = 'privatedns.zone'
    DEFAULT_DOMAIN_PUBLIC = 'publicdns.zone'

    def __init__(self, site, status, tenant, cluster, datazone, env, platform, role, backup, vcpus, memory, disk, ip_address: str = None, hostname: str = None):
        self.set_site(site)
        self.set_status(status)
        self.set_tenant(tenant)
        self.set_cluster(cluster)
        self.set_datazone(datazone)
        self.set_env(env)
        self.set_platform(platform)
        self.set_role(role)
        self.set_backup_tag(backup)
        self.set_vcpus(vcpus)
        self.set_memory(memory)
        self.set_disk(disk)
        self.set_hostname(hostname)
        self.set_ip_address(ip_address)

    def generate_hostname(self):
        # I now proclaim this VM, First of its Name, Queen of the Andals and the First Men, Protector of the Seven Kingdoms
        vm_index = "001"
        vm_search_for = "{0}-{1}-{2}-".format(self.site.slug, self.env.name.split('_')[1], self.role.name.split(':')[0])
        vms = VirtualMachine.objects.filter(
            name__startswith=vm_search_for
        )
        if len(vms) > 0:
            # Get last of its kind
            last_vm_index = int(vms[len(vms) - 1].name.split('-')[3]) + 1
            if last_vm_index < 10:
                vm_index = '00' + str(last_vm_index)
            elif last_vm_index < 100:
                vm_index = '0' + str(last_vm_index)
            else:
                vm_index = str(last_vm_index)
        # self.__staged_hostnames.append("{0}{1}".format(search_for, vm_index))
        return "{0}{1}".format(vm_search_for, vm_index)

    def get_vrf(self):
        return VRF.objects.get(
            name="global"
        )

    def get_fqdn(self):
        return "{}.{}".format(self.hostname, self.DEFAULT_DOMAIN_PRIVATE if netaddr.IPNetwork(self.ip_address.address).is_private() is True else self.DEFAULT_DOMAIN_PUBLIC)

    def set_ip_address(self, ip_address):
        try:
            ip_check = IPAddress.objects.filter(address=ip_address)
            if len(ip_check) > 0:
                raise Exception(str(ip_check[0].address) + ' is already assigned to ' + str(ip_check[0].interface.name))
            self.ip_address = IPAddress(
                address=ip_address,
                vrf=self.get_vrf(),
                tenant=self.tenant,
                family=4,
            )
            self.ip_address.dns_name = self.get_fqdn()
        except Exception as e:
            self.ip_address = None
            raise Exception("IP address - {0}".format(e))

    def set_hostname(self, hostname):
        try:
            self.hostname = hostname if hostname is not None else self.generate_hostname()
        except Exception as e:
            raise Exception("Hostname - {0}".format(e))

    def set_disk(self, disk):
        try:
            self.disk = disk
        except Exception as e:
            raise Exception("Disk - {0}".format(e))

    def set_memory(self, memory):
        try:
            self.memory = memory
        except Exception as e:
            raise Exception("Memory - {0}".format(e))

    def set_vcpus(self, vcpus):
        try:
            self.vcpus = vcpus
        except Exception as e:
            raise Exception("vcpus - {0}".format(e))

    def set_backup_tag(self, backup):
        try:
            self.backup = Tag.objects.filter(name="vsphere_tag_{0}".format(backup))[0]
        except Exception as e:
            raise Exception("Tag backup {0} does not exist, {1}".format(backup, e))

    def set_site(self, site):
        try:
            self.site = Site.objects.filter(
                name=site
            )[0]
        except Exception as e:
            raise Exception('Site does not exist - ' + str(e))

    def set_role(self, role):
        try:
            self.role = DeviceRole.objects.filter(
                name=role
            )[0]
        except Exception:
            self.role = None

    def set_platform(self, platform):
        try:
            self.platform = Platform.objects.filter(
                name=platform
            )[0]
        except Exception as e:
            raise Exception("Platform does not exist {0}".format(e))

    def set_env(self, env):
        try:
            self.env = Tag.objects.filter(name="env_{0}".format(env))[0]
        except Exception as e:
            raise Exception("Tag env does not exist - {0}".format(e))

    def set_datazone(self, datazone):
        try:
            self.datazone = Tag.objects.filter(name="datazone_{0}".format(datazone))[0]
        except Exception as e:
            raise Exception("Tag datazone does not exist - {0}".format(e))

    def set_cluster(self, cluster):
        try:
            self.cluster = Cluster.objects.filter(
                name=cluster
            )[0]
        except Exception as e:
            raise Exception("Cluster does not exist {0}".format(e))

    def set_tenant(self, tenant):
        try:
            self.tenant = Tenant.objects.filter(
                slug=tenant
            )[0]
        except Exception as e:
            raise Exception("Tenant does not exist {0}".format(e))

    def set_status(self, status):
        try:
            self.status = VirtualMachineStatusChoices.STATUS_STAGED if status == 'staged' else VirtualMachineStatusChoices.STATUS_PLANNED
        except Exception as e:
            raise Exception("Status does not exist {0}".format(e))

    # Assign IP to interface
    def create_interface(ip_address, data, vm):
        return True

    def __create_ip_address(self):
        self.ip_address.save()

    def __create_tags(self, vm: VirtualMachine):
        vm.tags.add(self.datazone)
        vm.tags.add(self.env)
        vm.tags.add(self.backup)
        for tag in self.DEFAULT_TAGS:
            vm.tags.add(tag)
        vm.save()

    def __create_vm(self):
        vm = VirtualMachine(
            status=self.status,
            cluster=self.cluster,
            platform=self.platform,
            role=self.role,
            tenant=self.tenant,
            name=self.hostname,
            disk=self.disk,
            memory=self.memory,
            vcpus=self.vcpus,
            primary_ip4=self.ip_address,
        )
        vm.save()
        return vm

    def __create_interface(self, vm: VirtualMachine):
        """
        Setup interface and add IP address
        """
        try:

            # Get net address tools
            ip = netaddr.IPNetwork(self.ip_address.address)
            prefix_search = str(ip.network) + '/' + str(ip.prefixlen)

            prefix = Prefix.objects.get(
                prefix=prefix_search,
                is_pool=True,
                site=self.site,
            )

            interfaces = vm.get_config_context().get('interfaces')

            interface = Interface(
                name=interfaces['nic0']['name'],
                mtu=interfaces['nic0']['mtu'],
                virtual_machine=vm,
                type=InterfaceTypeChoices.TYPE_VIRTUAL
            )

            # If we need anything other than Access, here is were to change it
            if interfaces['nic0']['mode'] == "Access":
                interface.mode = InterfaceModeChoices.MODE_ACCESS
                interface.untagged_vlan = prefix.vlan

            interface.save()

            self.ip_address.interface = interface
            self.ip_address.save()

        except Exception as e:
            raise Exception("Error while creating interface {}".format(e))
        return True

    def create(self):
        try:
            self.__create_ip_address()
            vm = self.__create_vm()
            self.__create_tags(vm)
            self.__create_interface(vm)
        except Exception as e:
            raise e
        return True


class BulkDeployVM(Script):
    """
    Example CSV :
    site,status,tenant,cluster,datazone,env,platform,role,backup,vcpus,memory,disk,hostname,ip_address
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,redirtp:v0.2.0,nobackup,1,1024,10,odn1-vlb-redirtp-001,10.50.61.10/24
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,consul:v1.0.1,backup_general_1,2,2048,20,odn1-vlb-consul-001,10.50.61.11/24
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,rediast:v0.2.0,backup_general_4,4,4096,30,odn1-vlb-rediast-001,10.50.61.12/24

    Example CSV (auto hostname):
    site,status,tenant,cluster,datazone,env,platform,role,backup,vcpus,memory,disk,ip_address
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,redirtp:v0.2.0,nobackup,1,1024,10,10.50.61.10/24
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,consul:v1.0.1,backup_general_1,2,2048,20,10.50.61.11/24
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,rediast:v0.2.0,backup_general_4,4,4096,30,10.50.61.12/24
    odn1,staged,patientsky-hosting,odn1,1,vlb,base:v1.0.0-coreos,rediast:v0.2.0,backup_general_4,4,4096,30,10.50.61.13/24
    """

    DEFAULT_CSV_FIELDS = "site,status,tenant,cluster,datazone,env,platform,role,backup,vcpus,memory,disk,hostname,ip_address"

    class Meta:
        name = "Bulk deploy new VMs"
        description = "Deploy new virtual machines from existing platforms"
        fields = ['vms']
        field_order = ['vms']
        commit_default = False

    vms = TextVar(
        label="Import",
        description="CSV import form.",
        required=True,
        default=DEFAULT_CSV_FIELDS
    )

    def get_vm_data(self):
        return self.vm_data

    def set_csv_data(self, vms):
        self.csv_raw_data = csv.DictReader(vms, delimiter=',')

    def get_csv_raw_data(self):
        return self.csv_raw_data

    def set(self, data):
        self.set_csv_data(data['vms'].splitlines())

    def run(self, data):

        self.set(data)

        i = 1
        for raw_vm in self.get_csv_raw_data():
            try:
                vm = VM(
                    site=raw_vm.get('site'),
                    status=raw_vm.get('status'),
                    tenant=raw_vm.get('tenant'),
                    cluster=raw_vm.get('cluster'),
                    datazone=raw_vm.get('datazone'),
                    env=raw_vm.get('env'),
                    platform=raw_vm.get('platform'),
                    role=raw_vm.get('role'),
                    backup=raw_vm.get('backup'),
                    vcpus=raw_vm.get('vcpus'),
                    memory=raw_vm.get('memory'),
                    disk=raw_vm.get('disk'),
                    hostname=raw_vm.get('hostname'),
                    ip_address=raw_vm.get('ip_address'),
                )
                vm.create()
                self.log_success("Created `{}`, IP `{}` to cluster `{}`".format(vm.get_fqdn(), vm.ip_address, vm.cluster))
                i = i + 1
            except Exception as e:
                self.log_failure("CSV line {}, Error while creating VM \n`{}`".format(i, e))
        return data['vms']
