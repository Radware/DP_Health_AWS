from pysnmp.entity.rfc3413.oneliner import cmdgen
import time
import boto3
import asyncio

def lambda_handler(event, context):
    print ("Starting keepalive")
    asyncio.run(get_host_list())


async def get_host_list():
    task_list = []
    client = boto3.client('ec2', 'us-east-2')
    # Locate instances with "DefenceProInstance" tag
    for tag in client.describe_tags(Filters=[{'Name': 'key','Values': ['DefenceProInstance']}])["Tags"]:
        print(tag)
        # Get instance information 
        instance_info = client.describe_instances(InstanceIds=[tag["ResourceId"]])
        try:
            # Loop through the interfaces searching for ETH1 (MGMT)
            for interface in instance_info["Reservations"][0]["Instances"][0]["NetworkInterfaces"]:
                if "Attachment" in interface and "DeviceIndex" in interface["Attachment"] and interface["Attachment"]["DeviceIndex"] == 1:
                    print("Found DP with MGMT IP = " + interface["PrivateIpAddress"])
                    task_list.append(asyncio.create_task(run_SNMP_test(interface["PrivateIpAddress"])))
        except Exception as e:
            print("[ERROR] unable to find network interface in instance info! instance ID: %s, error: %s " % (tag["ResourceId"],e))
    
    for task in task_list:
        await task

async def run_SNMP_test(host):
    oid = '1.3.6.1.4.1.89.35.1.112.0'
    community = 'public'
    repeat = 5
    for i in range(repeat):
        endtime = int(time.time()) + 10
        cmdGen = cmdgen.CommandGenerator()
        
        errorIndication, errorStatus, errorIndex, varBinds = cmdGen.getCmd(
        cmdgen.CommunityData(community),
        cmdgen.UdpTransportTarget((host, 161)),oid)

        # Check for errors and print out results
        if errorIndication:
            print(errorIndication)
        else:
            if errorStatus:
                print('%s at %s' % ( errorStatus.prettyPrint(),errorIndex and varBinds[int(errorIndex)-1] or '?') )
            else:
                value=str(varBinds[0][1])
                print("{ \"Description\": \"DefensePro Health Keep-Alive CPU query\", \"DefensePro IP\": \"%s\", \"value\": %s }" % (host, value))
        if endtime > int(time.time()):
            await asyncio.sleep(endtime-int(time.time()))
