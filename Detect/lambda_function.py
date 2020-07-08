from pysnmp.entity.rfc3413.oneliner import cmdgen
import time
import boto3
import asyncio

def lambda_handler(event, context):
    print ("[INFO] Starting DP Health Detector Lambda!")
    asyncio.run(get_host_list())

async def get_host_list():
    # Create a list to hold tasks per-dp
    task_list = []
    # Create EC2 client 
    client = boto3.client('ec2', 'us-east-2')
    # Locate instances with "DefenseProInstance" tag
    for tag in client.describe_tags(Filters=[{'Name': 'key','Values': ['DefenseProInstance']}])["Tags"]:
        # Get instance information 
        instance_info = client.describe_instances(InstanceIds=[tag["ResourceId"]])
        try:
            # Loop through the interfaces searching for ETH1 (MGMT)
            for interface in instance_info["Reservations"][0]["Instances"][0]["NetworkInterfaces"]:
                if "Attachment" in interface and "DeviceIndex" in interface["Attachment"] and interface["Attachment"]["DeviceIndex"] == 1:
                    print("[INFO] Found DP with MGMT IP = " + interface["PrivateIpAddress"])
                    # Create a task for running the tests
                    task_list.append(asyncio.create_task(run_test(interface["PrivateIpAddress"], tag['Value'])))
        except Exception as e:
            print(f"[ERROR] unable to find network interface in instance info! instance ID: {tag['ResourceId']}, error: {e} ")
    # execute the test tasks 
    for task in task_list:
        await task

async def run_test(host, dpName):
    oid = '.1.3.6.1.4.1.89.35.1.112'
    community = 'public'
    repeat = 90
    cloudwatch = boto3.client('cloudwatch')
    for i in range(repeat):
        # Mark estimated time for next iteration
        endtime = int(time.time()) + 10
        
        # Create SNMP Request
        cmdGen = cmdgen.CommandGenerator()
        errorIndication, errorStatus, errorIndex, varBinds = cmdGen.getCmd(
        cmdgen.CommunityData(community),
        cmdgen.UdpTransportTarget((host, 161), timeout=0, retries=0),oid)

        # Check for errors and print out results
        if errorIndication:
            print(f'{{ "Description": "DefensePro Health Keep-Alive CPU query", "Name": "{dpName}", "DefensePro IP": "{host}", "SNMP Error": {errorIndication} }}')
            response = cloudwatch.put_metric_data(
                MetricData = [ 
                    { 'MetricName': 'DP_KeepAlive_Timeouts', 'Dimensions': [
                        { 'Name': 'DefensePro_Name', 'Value': dpName },
                        { 'Name': 'DefensePro_IP', 'Value': host }
                    ],
                'Unit': 'None',
                'Value': 100
                }], Namespace = f'{dpName}_CPU' )

        else:
            if errorStatus:
                print('%s at %s' % ( errorStatus.prettyPrint(),errorIndex and varBinds[int(errorIndex)-1] or '?') )
            else:
                print(f'{{ "Description": "DefensePro Health Keep-Alive CPU query", "Name": "{dpName}", "DefensePro IP": "{host}", "SNMP_Result": {str(varBinds[0][1])} }}')
                response = cloudwatch.put_metric_data(
                    MetricData = [ 
                        { 'MetricName': 'DP_KeepAlive_Results', 'Dimensions': [
                            { 'Name': 'DefensePro_Name', 'Value': dpName },
                            { 'Name': 'DefensePro_IP', 'Value': host }
                        ],
                    'Unit': 'None',
                    'Value': int(varBinds[0][1])
                    }], Namespace = f'{dpName}_CPU' )
        # Run HTTP Test

        if endtime > int(time.time()):
            await asyncio.sleep(endtime-int(time.time()))

async def fetch_HTTP_Response(session, url):
    async with session.get(url) as response:
        await response.text()
        return response.status
