import json
import boto3

def lambda_handler(event, context):
    client = boto3.client('ec2')    
    ec2 = boto3.resource('ec2')
    lambda_client = boto3.client('lambda')

    print (event)
    dpName = ""
    dpIP = ""
    try:
        dpName = event["detail"]["configuration"]["metrics"][0]["metricStat"]["metric"]["dimensions"]["DefensePro_Name"]
        dpIP = event["detail"]["configuration"]["metrics"][0]["metricStat"]["metric"]["dimensions"]["DefensePro_IP"]
    except Exception as error:
        print(f'[ERROR] failed to get DP info! {error=}')
    
    vpcid, public_table, gw_tables, reals_tables, subnets, associd = fetch_ids(client, dpName)
    # print("finished getting table IDs")
    if "detail" in event and "state" in event["detail"] and "value" in event["detail"]["state"]:
        print(f'State of DP {dpName} \ {dpIP} has changed to {event["detail"]["state"]["value"]}')
        if event["detail"]["state"]["value"] == "ALARM":
            # environ = lambda_client.get_function_configuration( FunctionName='dp_ha_action_v2')
            response = lambda_client.get_function_configuration( FunctionName='dp_ha_action_v2')
            # print("got environment Variables")
            if not "Environment" in response or not "Variables" in response["Environment"]:
                environ = {}
            else:
                environ = response["Environment"]["Variables"]
            # Remove gateway association from the route-table
            if len(associd) > 1:
                response = client.disassociate_route_table(AssociationId=associd)
                environ[dpName+'_GatewayId'] = associd
                # print("finished disassociating GW route table")
            value = ""
            for id in reals_tables:
                if "SubnetId" in id and id["SubnetId"] != "":
                    response = client.disassociate_route_table(AssociationId=id["RouteTableAssociationId"])
                    # print(f'finished disassociating {id["SubnetId"]} route table')
                    if len(value) > 0:
                        value += environ[dpName+'_FailBackSubnets']+","
                    environ[dpName+'_FailBackSubnets'] = value+id["RouteTableAssociationId"]
            response = lambda_client.update_function_configuration( FunctionName='dp_ha_action_v2', Environment={ 'Variables': environ })
            # print("finished updating environment Variables")
        
            for subnet in subnets:
                response = client.associate_route_table(RouteTableId=public_table, SubnetId=subnet)
                # print(f"finished disassociating {subnet} route table")
        else:
            print(event)
    else:
        print (event)
    
    return 
def fetch_ids(client, dpName):
    vpcid=""    
    reals_tables=[]
    subnets=[]
    
    vpcid, public_table, associd = func_tableid_by_tag(client, 'DefenceProTable_', 'Public', vpcid)
    vpcid, gw_tables, associd = func_tableid_by_tag(client, 'DefenceProTable_', 'GatewayID', vpcid)

    response = client.describe_route_tables(Filters=[{'Name': 'tag:DefenceProTable_', 'Values': ['Reals']}])
    for table in response['RouteTables']:
        if 'RouteTableId' in table:
            reals_tables += table["Associations"]
        if 'VpcId' in table and table['VpcId'] != vpcid:
            print("[ERROR]: reals route table located in different VPC")
        if 'Associations' in table:
            for assoc in table['Associations']:
                if 'SubnetId' in assoc:
                    subnets.append(assoc['SubnetId'])
    
    return vpcid, public_table, gw_tables, reals_tables, subnets, associd

def func_tableid_by_tag(client, tag_name, tag_value, vpcid):
    response = client.describe_route_tables(Filters=[{'Name': 'tag:'+tag_name, 'Values': [tag_value]}])
    associd = ""
    tableid = ""
    if 'RouteTables' in response and len(response['RouteTables']) == 1:
        if 'RouteTableId' in response['RouteTables'][0]:
            tableid=response['RouteTables'][0]['RouteTableId']
        if 'VpcId' in response['RouteTables'][0]:
            if vpcid == "":
                vpcid = response['RouteTables'][0]['VpcId']
            elif vpcid != response['RouteTables'][0]['VpcId']:
                print("[ERROR]: VPC ID Mismatch! expected %s, but got %s" % (vpcid,response['RouteTables'][0]['VpcId']))
        if "Associations" in response['RouteTables'][0]:
            for assoc in response['RouteTables'][0]["Associations"]:
                if "GatewayId" in assoc:
                    associd = assoc['RouteTableAssociationId']
    elif 'RouteTables' in response and len(response['RouteTables']) > 1:
        print("[ERROR]: got more than one %s route table" % (tag_value))

    return vpcid, tableid, associd
