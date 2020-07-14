# DP_Health_AWS
DefensePro Health testing for AWS.

## Table Of Contents ###
- [Description](#description )
- [Detector Lambda](#detector-lambda)
  * [Subnet](#detector-lambda-subnet)
  * [Endpoints](#detector-lambda-endpoints)
  * [CloudWatch Rule](#detector-lambda-cloudwatch-rule)
  * [Permissions](#detector-lambda-permissions)
  * [Alarms](#detector-lambda-cloudwatch-alarms)
  * [Upload and Test](#detector-lambda-upload-and-test)
- [Action Lambda](#action-lambda)
  * [Permissions](#action-lambda-permissions)
  * [CloudWatch Rules](#action-lambda-cloudwatch-rules)

## Description ##
This repository holds the Lambda functions as well as their requirements for performing automatic bypass of DefensePro in AWS environment.
Before we begin, this solution assumes the following:
* All relevant objects are in the same VPC
* Protected objects (servers) are in a subnet which routing table points to the ENI of DefensePro - we will refer this routing table as `Reals`
* There is a routing table with the Internet Gateway assigned as the `Edge Gateway` with a route sending the Protected objects\their entire subnet to ENI of DefensePro - we will refer this routing table as `GatewayID`
* All Relevant route tables has a tag named `DefenseProTable`, the value represents the table type (F.E: for protected objects route table it would be `Reals`)

## Detector Lambda ##
The code, as well as the requirements are in `Detect` folder. This Lambda is responsible for:
1. Discovering the DefensePro devices based on a TAG `DefenseProInstance`
2. Quarrying the DefensePro devices with an SNMP request to the MGMT interface
3. Post results into CloudWatch log group.
4. Post results into CloudWatch metric.

<b>Note:</b> For achieving the above - this Lambda must be located in the same VPC as the DefensePro.

### Detector Lambda Subnet ###
Detector Lambda is going to require access to AWS API from within the VPC (more details in [Detector Lambda Endpoints](#detector-lambda-endpoints)).<br>
to make sure Lambda doesn't effect any other instances, it's recommended to use a separate subnet for this Lambda.

### Detector Lambda Endpoints ###
Detector Lambda performs several operations in AWS API (more details in [Detector Lambda Permissions](#detector-lambda-permissions))<br>
In order to gain access to AWS API from within the VPC Lambda requires an Endpoing matching the operation type.<br><br>
<b>Note:</b> in order to use Endpoints, DNS resolution and DNS hostname resolution must be enabled in the VPC.<br>
Create 2 endpoints:
1. com.amazonaws.us-east-2.ec2 - for the EC2 related operations
2. com.amazonaws.us-east-2.monitoring - for posting metric data into CloudWatch

each endpoint should be attached to the Lambda VPC and a security group allowes Lambda to send the APIs .

### Detector Lambda CloudWatch Rule ### 
Detector Lambda needs scheduled CloudWach rule, the rule will trigger Lambda function every 15 minutes
use the following expresion `0/15 * ? * * *` 

### Detector Lambda Permissions ###
The Lambda needs the following permissions:
* Create, Describe and Delete Network Interfaces - for being able to reside in a VPC
* Describe Tags - for getting a list of DP instances
* Describe Instance - for getting instance Interfaces information
* Put Metric Data - for posting results into CloudWatch Metrics

the following should be included into IAM policy Statements
```
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:CreateNetworkInterface",
                "ec2:DescribeInstances",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeTags",
                "ec2:DeleteNetworkInterface",
                "cloudwatch:PutMetricData"
            ],
            "Resource": "*"
        },
```

### Detector Lambda Upload and Test ###
To use the Detector Lambda all content of "Detect" directory should be uploaded into the AWS Lambda, it's recomended to create a ZIP file with the content and upload it.<br>
As the Lambda doesn't require any input, any test event configuration will trigger the script.
it's recomended to use the "Test" feature once to make sure the Metrics are created as well as making sure script is working as expected.

After making sure script is running as expected, to make sure one lambda will be always up - lambda timeout should be adjusted to 15 minutes.

In order to oporate in an environment with more than one DefernsePro in different VPC - create an environment variable valled `VpcId` (case sensitive) with the VPC as the Value.

### Detector Lambda CloudWatch Alarms ###
CloudWatch Alarm is used for setting thresholds on each of the metrics. <br>
A separate Alarm shloud be created for each metric (it's recomended to set norification to all Alerts).<br>

## Action Lambda ## 
this Lambda is responsible for:
1. discovering all relevant route tables (based on tags)
2. replace association between Public and Protected object route table (for passing or bypassing the DefensePro)
3. removal or association of the internet gateway from the `GatewayID` route table (for passing or bypassing the DefensePro)

### Action Lambda CloudWatch Rules ###
For performing the acctual bypass operation, use an additional Rule triggering Action Lambda on <b>any</b> alarm change.<br>

### Action Lambda Permissions ###
In order to oporate the Lambda needs the following permissions:
```
    "Effect": "Allow",
    "Action": [
        "ec2:DescribeInternetGateways",
        "logs:CreateLogStream",
        "ec2:DeleteTags",
        "ec2:DescribeTags",
        "ec2:CreateTags",
        "ec2:DisassociateRouteTable",
        "logs:CreateLogGroup",
        "logs:PutLogEvents",
        "ec2:DescribeRouteTables",
        "ec2:AssociateRouteTable"
    ],
    "Resource": "*"
```
