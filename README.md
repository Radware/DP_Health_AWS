# DP_Health_AWS
DefensePro Health testing for AWS.

## Table of Contents ###
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
  * [Upload](#action-lambda-upload)

## Description ##
This repository holds the Lambda functions as well as their requirements for performing automatic bypass of DefensePro in AWS environment.
Before we begin, this solution assumes the following:
* All relevant objects are in the same VPC
* Protected objects (servers) are in a subnet which the routing table points to the ENI of DefensePro. We refer to this routing table as `Reals`
* There is a routing table with the Internet Gateway assigned as the `Edge Gateway` with a route sending the Protected objects\their entire subnet to ENI of DefensePro. We refer to this routing table as `GatewayID`
* All Relevant route tables have a tag named `DefenseProTable`, The value represents the table type (For example, for protected objects route table it would be `Reals`)
* For the HTTP, every DefensePro instance should have a tag `DefenseProHealthURL` containing the URL lambda will use for testing the DefensePro instances. Make sure Lambda subnet has a route forcing URL destination to DefensePro NIC 

## Detector Lambda ##
The Detect Lambda has two flavors, one is SNMP only and the other is combination of SNMP with an HTTP/S request through DefensePro.

<b>SNMP only flavor:</b><br>
The script as well as the requirements are in `Detect_SNMP` directory, This Lambda is responsible for:
1. Discovering the DefensePro devices based on a TAG `DefenseProInstance`
2. Quarrying the DefensePro devices with an SNMP request to the MGMT interface
3. Post logs into CloudWatch log group.
4. Post results into CloudWatch metric.

<b>SNMP + HTTP flavor:</b><br>
The script as well as the requirements are in `Detect_SNMP_and_HTTP` directory, This Lambda is responsible for:
1. Discovering the DefensePro devices based on a TAG `DefenseProInstance`
2. Quarrying the DefensePro devices with an SNMP request to the MGMT interface
2. Issue an HTTP/S request to a URL provided in `DefenseProHealthURL` tag on the DefensePro instance
3. Post logs into CloudWatch log group.
4. Post results into CloudWatch metric.

<b>Results:</b><br>
SNMP only creates two separate metrics - one containing the SNMP result and the other is an integer (0 if there was no timeout and 100 in case SNMP query timedout).<br>
SNMP + HTTP creates one metric only an integer, 0 for doing nothing and 10 for triggering the Action (if SNMP result is above 80 <b>or</b> HTTP/S query has failed)

<b>Note:</b> 
* This Lambda must be located in the same VPC as the DefensePro.
* CloudWatch rule should be created for each metric (For more details, see [CloudWatch Rule](#detector-lambda-cloudwatch-rule))
* For the HTTP/S test to be effective, the Lambda subnet must route the HTTP/S destination to DefensePro NIC, thus making sure request is routed through DefensePro.


### Detector Lambda Subnet ###
Detector Lambda is going to require access to AWS API from within the VPC (more details in [Detector Lambda Endpoints](#detector-lambda-endpoints)).<br>
To make sure Lambda doesn't affect any other instances, it is recommended to use a separate subnet for this Lambda.

### Detector Lambda Endpoints ###
Detector Lambda performs several operations in AWS API. (For more details, see [Detector Lambda Permissions](#detector-lambda-permissions))<br>
In order to gain access to AWS API from within the VPC, Lambda requires an endpoint matching the operation type.

<b>Note:</b> In order to use endpoints, DNS resolution and DNS hostname resolution must be enabled in the VPC.<br>
Create two endpoints:
1. com.amazonaws.REGION.ec2 - for the EC2 related operations 
2. com.amazonaws.REGION.monitoring - for posting metric data into CloudWatch

Each endpoint should be attached to the Lambda VPC and a security group allows Lambda to send the APIs .

### Detector Lambda CloudWatch Rule ### 
Detector Lambda needs scheduled CloudWach rule. The rule will trigger a Lambda function every 15 minutes. <br>
Use the following expression `0/15 * ? * * *` 

### Detector Lambda Permissions ###
The Lambda needs the following permissions:
* Create, Describe and Delete Network Interfaces - for being able to reside in a VPC
* Describe Tags - for getting a list of DP instances
* Describe Instance - for getting instance Interfaces information
* Put Metric Data - for posting results into CloudWatch Metrics

The following should be included into IAM policy statements
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
To use the Detector Lambda all content of "Detect_SNMP_and_HTTP" directory should be uploaded into the AWS Lambda. It is recommended to create and upload a ZIP file with the content.<br>
As the Lambda doesn't require any input, any test event configuration will trigger the script. <br>
It is recommended to use the "Test" feature once to make sure the Metrics are created as well as making sure the script is working as expected.

After making sure script is running as expected, to make sure one Lambda will be always up, Lambda timeout should be adjusted to 15 minutes.

In order to operate in an environment with more than one DefernsePro in different VPCs, create an environment variable valled VpcId (case sensitive) with the VPC as the Value.

### Detector Lambda CloudWatch Alarms ###
CloudWatch Alarm is used for setting thresholds on each of the metrics.<br>
A separate Alarm should be created for each metric. (It is recommended to set notification to all Alerts.).

## Action Lambda ## 
This Lambda is responsible for:
1. discovering all relevant route tables (based on tags)
2. replacing association between Public and Protected object route table (for passing or bypassing the DefensePro)
3. removing or associating of the internet gateway from the `GatewayID` route table (for passing or bypassing the DefensePro)

### Action Lambda CloudWatch Rules ###
For performing the actual bypass operation, use an additional Rule triggering Action Lambda on any change of the alarm configured in step [Alarms](#detector-lambda-cloudwatch-alarms) .<br>
The rule should be `event pattern` and configured with custom event pointing to the alarms, for example:
```
{
  "source": [
    "aws.cloudwatch"
  ],
  "resources": [
    "arn:aws:cloudwatch:REGION:ACCOUNT-ID:alarm:ALARM 1 NAME",
    "arn:aws:cloudwatch:REGION:ACCOUNT-ID:alarm:ALARM 2 NAME"
  ],
  "detail-type": [
    "CloudWatch Alarm State Change"
  ]
}
```

### Action Lambda Permissions ###
In order to operate the action Lambda function needs the following permissions:
* Describe Internet Gateways - to fetch internet gateway information 
* Get and Update lambda function configuration - to modify environment variables in case failback is needed
* Describe, associate and disassociate route tables - for performing the actual bypass operation 

The following should be included in IAM policy statements

```
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInternetGateways",
                "lambda:UpdateFunctionConfiguration",
                "lambda:GetFunctionConfiguration",
                "ec2:DisassociateRouteTable",
                "ec2:DescribeRouteTables",
                "ec2:AssociateRouteTable"
            ],
            "Resource": "*"
        }
```

### Action Lambda Upload ###
Unlike the Detect, action lambda uses builtin modules only, hence to use the Action Lambda only the `DP_HA_Action.py` should be uploaded to AWS Lambda.<br>
To make sure the Lambda subnet is skipped when performing route table changes, the lambda expects an environment variable `LambdaSubnetId` holding the ID of the detector lambda.