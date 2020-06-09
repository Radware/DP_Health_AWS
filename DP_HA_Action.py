import json
import boto3

def lambda_handler(event, context):
    client = boto3.client('ec2')    
    ec2 = boto3.resource('ec2')

    vpcid, public_table, gw_tables, reals_tables, subnets = fetch_ids(client)
    print (event)
    if "detail" in event and "state" in event["detail"] and "value" in event["detail"]["state"]:
        if event["detail"]["state"]["value"] == "OK":
            subnet_assoc_map = {}
            for table in client.describe_route_tables(RouteTableIds=[public_table])["RouteTables"]:
                for assoc in table["Associations"]:
                    if "SubnetId" in assoc:
                        subnet_assoc_map.update({assoc["SubnetId"]: assoc["RouteTableAssociationId"]})
            # print(subnet_assoc_map)
            tag_response = client.describe_tags(Filters=[{'Name': 'key','Values': ['DefenceProFailBackSubnets']}, {'Name': 'resource-id', 'Values': [reals_tables[0]]}])
            # print(response)
            if "Tags" in tag_response and "Value" in tag_response["Tags"][0]:
                for subnet in filter(None, tag_response["Tags"][0]["Value"].split(',')):
                    if subnet in subnet_assoc_map:
                        # print(subnet_assoc_map[subnet])
                        response = client.disassociate_route_table(AssociationId=subnet_assoc_map[subnet])
                    else:
                        print("[ERROR] did not find RouteTableAssociationId for subnet %s" % subnet)
                    response = client.associate_route_table(RouteTableId=reals_tables[0], SubnetId=subnet)
                client.delete_tags(Tags=[{"Key": tag_response["Tags"][0]["Key"], "Value": tag_response["Tags"][0]["Value"]}], Resources=[reals_tables[0]])

            igw = client.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id','Values': [vpcid]}])
            if "InternetGatewayId" in igw["InternetGateways"][0]:
                response = client.associate_route_table(RouteTableId=gw_tables, GatewayId=igw["InternetGateways"][0]["InternetGatewayId"])

        elif event["detail"]["state"]["value"] == "INSUFFICIENT_DATA" or event["detail"]["state"]["value"] == "ALARM":
            # get RouteTableAssociationId
            route_tables = client.describe_route_tables(RouteTableIds=[gw_tables])
            # Remove gateway association from the route-table
            for table in route_tables["RouteTables"]:
                for id in table["Associations"]:
                    if "GatewayId" in id and id["GatewayId"] != "":
                        response = client.disassociate_route_table(AssociationId=id["RouteTableAssociationId"])
            for real_table in reals_tables:
                route_tables = client.describe_route_tables(RouteTableIds=[real_table])
                for table in route_tables["RouteTables"]:
                    for id in table["Associations"]:
                        if "SubnetId" in id and id["SubnetId"] != "":
                            response = client.disassociate_route_table(AssociationId=id["RouteTableAssociationId"])
                            value=""
                            response = client.describe_tags(Filters=[{'Name': 'key','Values': ['DefenceProFailBackSubnets']}, {'Name': 'resource-id', 'Values': [real_table]}])
                            if len(response["Tags"])>0 and "Value" in response["Tags"][0]:
                                value=response["Tags"][0]["Value"]
                                client.delete_tags(Tags=[{"Key": response["Tags"][0]["Key"], "Value": response["Tags"][0]["Value"]}], Resources=[real_table])
                            response = ec2.create_tags(Resources=[real_table], Tags=[{'Key': 'DefenceProFailBackSubnets','Value': value+","+id["SubnetId"]}])

            for subnet in subnets:
                response = client.associate_route_table(RouteTableId=public_table, SubnetId=subnet)
        else:
            print(event)
    else:
        print (event)


    # TODO implement
    return {
        'statusCode': 200,
        'body': event
    }

def fetch_ids(client):
    vpcid=""    
    reals_tables=[]
    subnets=[]
    
    vpcid, public_table = func_tableid_by_tag(client, 'DefenceProTable', 'Public', vpcid)
    vpcid, gw_tables = func_tableid_by_tag(client, 'DefenceProTable', 'GatewayID', vpcid)

    response = client.describe_route_tables(Filters=[{'Name': 'tag:DefenceProTable', 'Values': ['Reals']}])
    for table in response['RouteTables']:
        if 'RouteTableId' in table:
            reals_tables.append(table['RouteTableId'])
        if 'VpcId' in table and table['VpcId'] != vpcid:
            print("[ERROR]: reals route table located in different VPC")
        if 'Associations' in table:
            for assoc in table['Associations']:
                if 'SubnetId' in assoc:
                    subnets.append(assoc['SubnetId'])
    
    return vpcid, public_table, gw_tables, reals_tables, subnets

def func_tableid_by_tag(client, tag_name, tag_value, vpcid):
    response = client.describe_route_tables(Filters=[{'Name': 'tag:'+tag_name, 'Values': [tag_value]}])
    if 'RouteTables' in response and len(response['RouteTables']) == 1:
        if 'RouteTableId' in response['RouteTables'][0]:
            tableid=response['RouteTables'][0]['RouteTableId']
        if 'VpcId' in response['RouteTables'][0]:
            if vpcid == "":
                vpcid = response['RouteTables'][0]['VpcId']
            elif vpcid != response['RouteTables'][0]['VpcId']:
                print("[ERROR]: VPC ID Mismatch! expected %s, but got %s" % (vpcid,response['RouteTables'][0]['VpcId']))
    elif 'RouteTables' in response and len(response['RouteTables']) > 1:
        print("[ERROR]: got more than one %s route table" % (tag_value))

    return vpcid, tableid
